import base64
import json
from openai import OpenAI
from core.config import settings

openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

def transcribe_audio_whisper(audio_path: str):
    """
    Transcribe audio with Whisper and return word-level timestamps.
    Then, extracts keywords and overall tone.
    """
    with open(audio_path, "rb") as audio_file:
        transcript = openai_client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )
    
    # Extract tone and main keywords by feeding transcript text to a fast model (GPT-4o-mini or 3.5)
    prompt = f"""
    Analyze the following audio transcript.
    Identify the overall tone from these options: [energetic, emotional, informational, urgent]
    Identify up to 10 key words from the text that represent the most important visual topics.
    Crucial: For each keyword, give the 'original_word' EXACTLY as it appears in the transcript, and its 'english_translation'. 
    Respond ONLY with a JSON object: {{"tone": "...", "keywords": [{{"original_word": "...", "english_translation": "..."}}]}}
    
    Transcript: {transcript.text}
    """
    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini", # text works perfectly on 4o-mini too, preventing 5-mini issues
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}]
    )
    analysis = json.loads(completion.choices[0].message.content)
    
    # Map back top_keywords to their actual timestamps in the transcript
    matched_keywords = []
    
    keyword_list = analysis.get("keywords", [])
    target_map = {item.get("original_word", "").lower(): item.get("english_translation", "").lower() for item in keyword_list}
    
    # Collect ALL word timestamps for rhythm analysis
    all_words = []
    for word_info in transcript.words:
        clean_word = word_info.word.strip(".,!?\"'").lower()
        all_words.append({
            "word": word_info.word.strip(),
            "start": word_info.start,
            "end": word_info.end
        })
        if clean_word in target_map:
            matched_keywords.append({
                "word": target_map[clean_word],
                "timestamp_start": word_info.start,
                "timestamp_end": word_info.end
            })

    return {
        "text": transcript.text,
        "duration_seconds": transcript.duration,
        "keywords": matched_keywords,
        "tone": analysis.get("tone", "informational"),
        "all_words": all_words
    }

def analyze_speech_rhythm(all_words: list[dict], total_duration: float) -> list[dict]:
    """
    Analyzes word-level timestamps to detect natural phrase boundaries.
    Returns a list of phrases with timing, text, and speech pace.
    Pure Python math — zero API calls.
    """
    if not all_words:
        return []
    
    PAUSE_THRESHOLD = 0.35  # seconds — a gap bigger than this = new phrase
    
    phrases = []
    current_phrase_words = [all_words[0]]
    
    for i in range(1, len(all_words)):
        gap = all_words[i]["start"] - all_words[i-1]["end"]
        
        if gap >= PAUSE_THRESHOLD:
            # Natural pause detected — end current phrase
            phrase_start = current_phrase_words[0]["start"]
            phrase_end = current_phrase_words[-1]["end"]
            phrase_duration = phrase_end - phrase_start
            words_per_sec = len(current_phrase_words) / max(phrase_duration, 0.1)
            
            phrases.append({
                "text": " ".join(w["word"] for w in current_phrase_words),
                "start_sec": round(phrase_start, 2),
                "end_sec": round(phrase_end, 2),
                "duration": round(phrase_duration, 2),
                "word_count": len(current_phrase_words),
                "pace": "fast" if words_per_sec > 3.5 else "slow" if words_per_sec < 2.0 else "normal"
            })
            current_phrase_words = []
        
        current_phrase_words.append(all_words[i])
    
    # Don't forget the last phrase
    if current_phrase_words:
        phrase_start = current_phrase_words[0]["start"]
        phrase_end = current_phrase_words[-1]["end"]
        phrase_duration = phrase_end - phrase_start
        words_per_sec = len(current_phrase_words) / max(phrase_duration, 0.1)
        
        phrases.append({
            "text": " ".join(w["word"] for w in current_phrase_words),
            "start_sec": round(phrase_start, 2),
            "end_sec": round(phrase_end, 2),
            "duration": round(phrase_duration, 2),
            "word_count": len(current_phrase_words),
            "pace": "fast" if words_per_sec > 3.5 else "slow" if words_per_sec < 2.0 else "normal"
        })
    
    return phrases

def analyze_audio_aida(transcript_text: str, duration_seconds: float) -> list[dict]:
    """
    Step 1: Analyze the audio transcript to identify AIDA phases with exact timestamps.
    Returns a list of phases with timing, visual direction, and what to show.
    """
    prompt = f"""You are an expert in direct-response advertising. Analyze this audio transcript and identify the AIDA phases.

TRANSCRIPT:
"{transcript_text}"

TOTAL DURATION: {round(duration_seconds, 1)} seconds

Break this transcript into AIDA phases. For EACH phase, provide:
1. The phase name (attention, interest, desire, action)
2. The exact start and end timestamps (in seconds)
3. A brief summary of what the narrator is saying
4. What TYPE of visual should accompany this phase (be very specific)

IMPORTANT RULES:
- ATTENTION phase: The narrator talks about problems/pain points. Visuals should show people SUFFERING those problems (discomfort, frustration, awkward situations). Do NOT show the product.
- INTEREST phase: The narrator introduces the solution/product. Visuals should show the product being revealed or unboxed for the first time.
- DESIRE phase: The narrator describes benefits. Visuals should show people HAPPY using the product, comfortable, relaxed.
- ACTION phase: Call to action, discounts. Visuals should show promotional graphics, prices, urgency.
- The phases must be sequential and cover the ENTIRE duration with no gaps.
- Each phase can have sub-sections if the narrator switches topics within the same phase.

Respond ONLY with a JSON object:
{{"phases": [
  {{"phase": "attention", "start_sec": 0.0, "end_sec": 8.0, "narrator_says": "talks about neck pain during travel", "visual_direction": "Show people with neck pain, uncomfortable in airplane seats, sleeping on strangers"}},
  {{"phase": "interest", "start_sec": 8.0, "end_sec": 15.0, "narrator_says": "introduces the travel pillow", "visual_direction": "Show the product being unboxed, first reveal"}}
]}}"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are an AIDA advertising framework expert. Respond only in valid JSON."},
            {"role": "user", "content": prompt}
        ]
    )
    
    try:
        data = json.loads(response.choices[0].message.content)
        return data.get("phases", [])
    except:
        # Fallback: split evenly into 4 phases
        q = duration_seconds / 4
        return [
            {"phase": "attention", "start_sec": 0, "end_sec": q, "narrator_says": "hook", "visual_direction": "Show problems"},
            {"phase": "interest", "start_sec": q, "end_sec": q*2, "narrator_says": "solution", "visual_direction": "Show product"},
            {"phase": "desire", "start_sec": q*2, "end_sec": q*3, "narrator_says": "benefits", "visual_direction": "Show benefits"},
            {"phase": "action", "start_sec": q*3, "end_sec": duration_seconds, "narrator_says": "cta", "visual_direction": "Show promo"},
        ]

def generate_phrase_visual_directions(phrases: list[dict], aida_phases: list[dict], transcript_text: str) -> list[dict]:
    """
    For each speech phrase, generates a specific English visual description
    of what B-roll should show. Uses GPT-4o-mini in a single batch call.
    Returns the phrases enriched with 'visual_description' and 'aida_phase'.
    """
    if not phrases:
        return []

    # Assign AIDA phase to each phrase by timestamp
    for phrase in phrases:
        phrase_mid = phrase["start_sec"] + (phrase.get("duration", 1.0) / 2.0)
        phrase["aida_phase"] = "attention"  # default
        for ap in aida_phases:
            if ap.get("start_sec", 0.0) <= phrase_mid <= ap.get("end_sec", 9999):
                phrase["aida_phase"] = ap.get("phase", "attention")
                break

    # Build batch prompt
    phrase_list_str = ""
    for i, p in enumerate(phrases):
        phrase_list_str += f'{i+1}. [{p["aida_phase"].upper()}] ({p["start_sec"]:.1f}s - {p["end_sec"]:.1f}s): "{p["text"]}"\n'

    prompt = f"""You are a video director choosing B-roll footage for a direct-response ad.

FULL SCRIPT (for context — the language may be Spanish or another language):
"{transcript_text}"

Below are the individual phrases of the script, each tagged with its AIDA advertising phase.
For EACH phrase, write a concrete, literal ENGLISH description of the B-roll scene that should accompany it.

RULES:
- ATTENTION phrases: Show people experiencing the PROBLEM described (discomfort, frustration, awkward situations). NO product.
- INTEREST phrases: Show the product being revealed, unboxed, or introduced for the first time.
- DESIRE phrases: Show people HAPPILY using the product, enjoying the benefits, looking comfortable/relaxed.
- ACTION phrases: Show urgency cues — discounts, limited stock, website, call-to-action overlays.
- Be extremely specific and literal: describe physical actions, body positions, facial expressions, settings, objects.
- Each description should be 1-2 sentences in English.
- Focus on what a camera would CAPTURE, not abstract concepts.

PHRASES:
{phrase_list_str}
Respond ONLY with a JSON object:
{{"visual_directions": ["description for phrase 1", "description for phrase 2", ...]}}"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=2000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a professional video director. Respond only in valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        data = json.loads(response.choices[0].message.content)
        directions = data.get("visual_directions", [])

        for i, phrase in enumerate(phrases):
            if i < len(directions):
                phrase["visual_description"] = directions[i]
            else:
                phrase["visual_description"] = f"Generic {phrase['aida_phase']} phase visual"
    except Exception as e:
        # Fallback: use AIDA phase visual_direction
        for phrase in phrases:
            matching_aida = next((ap for ap in aida_phases if ap.get("phase") == phrase.get("aida_phase")), None)
            phrase["visual_description"] = matching_aida.get("visual_direction", "General scene") if matching_aida else "General scene"

    return phrases


def analyze_video_gemini(video_path: str, product_image_path: str = None) -> list[dict]:
    """
    Uses Gemini 2.5 Flash native File API to extract B-Roll segments with full context.
    """
    import time
    from google import genai
    from google.genai import types
    from core.config import settings
    import logging
    logger = logging.getLogger(__name__)

    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set.")
        return []

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    product_rules = ""
    if product_image_path:
        product_rules = "CRITICAL RULE: An image of the SPECIFIC reference product is attached to this prompt! You MUST set 'contains_reference_product' to TRUE if and only if the main object in the video scene EXACTLY visually matches this attached reference image."
    else:
        product_rules = "Since no reference image was provided, set 'contains_reference_product' to false for all segments."
    
    system_prompt = f"""You are an expert video analyst extracting literal visual descriptions for a Semantic Search database.

Watch this entire video carefully and break it into ALL distinct shots and clips.
CRITICAL RULE: Every time there is a camera cut, angle change, or scene shift — YOU MUST create a new segment. Be AGGRESSIVE about cutting.
Target 1 to 4 seconds per segment. Do NOT lump different shots together into one long segment.

{product_rules}

For EACH segment provide its EXACT start and end timestamps and a highly literal, objective visual description.
Do NOT use marketing language. Describe exactly: who is in frame, what they are doing, their facial expression, body position, setting, and visible objects.

Respond ONLY with a JSON array:
[
  {{
    "start_sec": 0.0,
    "end_sec": 2.5,
    "description": "A literal 2-sentence description of the physical actions, people, expressions, and objects visible in this exact shot.",
    "mood": "one of: frustrated, uncomfortable, happy, calm, excited, neutral, painful, surprised, tired",
    "keywords": ["woman", "bus", "sleeping", "shoulder", "stranger"],
    "contains_reference_product": false
  }}
]
For "mood" choose the single most accurate emotional tone. For "keywords" list 4-6 concrete nouns/verbs visible (in English).
CRITICAL: The entire duration of the video must be covered sequentially without leaving gaps. Pay close attention to visual cuts."""

    gemini_uploads = []
    try:
        # 1. Upload the main video
        print(f"[GEMINI] Uploading {video_path}...")
        video_file = client.files.upload(path=video_path)
        gemini_uploads.append(video_file)
        
        # Wait for video processing
        while video_file.state == "PROCESSING":
            print("[GEMINI] Waiting for video processing...")
            time.sleep(2)
            video_file = client.files.get(name=video_file.name)
            
        if video_file.state == "FAILED":
            print("[GEMINI] Video processing failed on Google servers.")
            return []

        # 3. Request Analysis
        print("[GEMINI] Analyzing video structure...")
        
        prompt_contents = [video_file, system_prompt]
        if product_image_path:
            # Inject native PIL Image instead of using File API to prevent GRPC Data errors
            try:
                from PIL import Image
                ref_img = Image.open(product_image_path)
                prompt_contents.insert(1, ref_img)
                print(f"[GEMINI] Successfully injected PIL reference image!")
            except Exception as e:
                print(f"[GEMINI] Failed to load reference image via PIL: {e}")
        
        import random
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
                break # Success
            except Exception as inner_e:
                err_str = str(inner_e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries - 1:
                        # Prevent Thundering Herd collisions by staggering wake times past the 60s quota limit
                        sleep_time = 65 + random.randint(5, 30)
                        print(f"[GEMINI] Rate Limit Hit (429). Staggering retry in {sleep_time}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(sleep_time)
                    else:
                        print("[GEMINI] Max retries exhausted for rate limits.")
                        raise inner_e # Throw out if still failing
                else:
                    raise inner_e # If it's a 400 or other error, crash instantly
        
        # 4. Clean up the file from Google servers
        try:
            client.files.delete(name=video_file.name)
        except:
            pass
            
        data = json.loads(response.text)
        print(f"[GEMINI] Success! Found {len(data)} segments in video.")
        return data
        
    except Exception as e:
        print(f"[GEMINI] Failure: {str(e)}")
        return []
