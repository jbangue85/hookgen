import json
import math
import logging
from services.ai_services import openai_client

logger = logging.getLogger(__name__)

# Expected moods per AIDA phase for mood-matching bonus
AIDA_MOOD_MAP = {
    "attention": {"frustrated", "uncomfortable", "painful", "tired", "surprised"},
    "interest": {"neutral", "surprised", "excited", "calm"},
    "desire": {"happy", "calm", "excited"},
    "action": {"excited", "happy", "surprised"},
}


def get_embedding(text: str) -> list[float]:
    """Fetches the 1536-dimensional vector embedding using text-embedding-3-small."""
    try:
        response = openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"[MATCH] Error generating embedding: {e}")
        return [0.0] * 1536


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Batch embedding call — cheaper and faster than one-by-one."""
    if not texts:
        return []
    try:
        response = openai_client.embeddings.create(
            input=texts,
            model="text-embedding-3-small"
        )
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
    except Exception as e:
        logger.error(f"[MATCH] Error generating batch embeddings: {e}")
        return [[0.0] * 1536] * len(texts)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calculates the mathematical similarity between two vectors (-1.0 to 1.0)."""
    dot_product = sum(x * y for x, y in zip(v1, v2))
    mag1 = math.sqrt(sum(x * x for x in v1))
    mag2 = math.sqrt(sum(x * x for x in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def _build_timeline_slots(phrases: list[dict], total_audio_duration: float) -> list[dict]:
    """
    Convert speech phrases into timeline slots.
    - Merges very short phrases (<1.0s) with the next one
    - Splits very long phrases (>6.0s) at the midpoint
    - Fills gaps between phrases by extending the previous slot
    """
    if not phrases:
        return []

    # Merge short phrases
    merged = []
    i = 0
    while i < len(phrases):
        p = dict(phrases[i])
        # Merge forward if too short and there's a next phrase
        while p.get("duration", p["end_sec"] - p["start_sec"]) < 1.0 and i + 1 < len(phrases):
            i += 1
            next_p = phrases[i]
            p["text"] = p.get("text", "") + " " + next_p.get("text", "")
            p["end_sec"] = next_p["end_sec"]
            p["duration"] = p["end_sec"] - p["start_sec"]
            p["visual_description"] = p.get("visual_description", "") + " " + next_p.get("visual_description", "")
            # Keep the aida_phase of the first phrase
        merged.append(p)
        i += 1

    # Split long phrases and fill gaps
    slots = []
    for j, p in enumerate(merged):
        # Fill gap from previous slot end to this phrase start
        if slots and p["start_sec"] > slots[-1]["end"]:
            slots[-1]["end"] = p["start_sec"]
            slots[-1]["duration"] = slots[-1]["end"] - slots[-1]["start"]

        duration = p["end_sec"] - p["start_sec"]
        if duration > 6.0:
            mid = p["start_sec"] + duration / 2.0
            slots.append({
                "start": p["start_sec"], "end": mid,
                "duration": mid - p["start_sec"],
                "visual_description": p.get("visual_description", ""),
                "aida_phase": p.get("aida_phase", "attention"),
            })
            slots.append({
                "start": mid, "end": p["end_sec"],
                "duration": p["end_sec"] - mid,
                "visual_description": p.get("visual_description", ""),
                "aida_phase": p.get("aida_phase", "attention"),
            })
        else:
            slots.append({
                "start": p["start_sec"], "end": p["end_sec"],
                "duration": duration,
                "visual_description": p.get("visual_description", ""),
                "aida_phase": p.get("aida_phase", "attention"),
            })

    # Fill initial gap if first phrase doesn't start at 0
    if slots and slots[0]["start"] > 0.1:
        slots[0]["start"] = 0.0
        slots[0]["duration"] = slots[0]["end"] - slots[0]["start"]

    # Extend last slot to cover full audio duration
    if slots and slots[-1]["end"] < total_audio_duration:
        slots[-1]["end"] = total_audio_duration
        slots[-1]["duration"] = slots[-1]["end"] - slots[-1]["start"]

    return slots


def select_best_clips(segments: list[dict], phrases: list[dict], aida_phases: list[dict], total_audio_duration: float) -> list[dict]:
    """
    Phrase-based semantic matching: matches each speech phrase to the
    best-fitting video segment using cosine similarity on visual descriptions.
    """
    if not segments:
        logger.error("[MATCH] No video segments available.")
        return []
    if not phrases:
        logger.error("[MATCH] No speech phrases available.")
        return []

    # 1. Build timeline slots from speech phrases
    slots = _build_timeline_slots(phrases, total_audio_duration)
    logger.warning(f"[MATCH] Created {len(slots)} timeline slots from speech phrases")

    # 2. Batch-embed all segment descriptions
    logger.warning(f"[MATCH] Vectorizing {len(segments)} B-Roll segments...")
    seg_texts = [f"Visual scene: {seg.get('description', '')}" for seg in segments]
    seg_vectors = get_embeddings_batch(seg_texts)
    for i, seg in enumerate(segments):
        seg["vector"] = seg_vectors[i]
        seg["used_count"] = 0
        seg["index"] = i

    # 3. Batch-embed all phrase visual descriptions
    logger.warning(f"[MATCH] Vectorizing {len(slots)} phrase visual directions...")
    phrase_texts = [slot.get("visual_description", "") for slot in slots]
    phrase_vectors = get_embeddings_batch(phrase_texts)
    for i, slot in enumerate(slots):
        slot["vector"] = phrase_vectors[i]

    # 4. Score and assign: for each slot pick the best segment
    logger.warning("[MATCH] Running phrase-by-phrase cosine matching...")
    best_cuts = []
    prev_seg_index = None

    for slot_idx, slot in enumerate(slots):
        target_vector = slot["vector"]
        aida_phase = slot.get("aida_phase", "attention")
        expected_moods = AIDA_MOOD_MAP.get(aida_phase, set())

        ranked = []
        for seg in segments:
            score = cosine_similarity(target_vector, seg["vector"])

            # Keyword overlap bonus
            seg_keywords = seg.get("keywords", [])
            vis_desc_lower = slot.get("visual_description", "").lower()
            if seg_keywords and vis_desc_lower:
                overlap = sum(1 for kw in seg_keywords if kw.lower() in vis_desc_lower)
                score += min(overlap * 0.05, 0.15)

            # Mood match bonus
            seg_mood = seg.get("mood", "").lower()
            if seg_mood and seg_mood in expected_moods:
                score += 0.05

            # Product rules
            has_product = seg.get("contains_reference_product", False)
            if aida_phase == "attention" and has_product:
                score -= 0.5
            elif aida_phase in ("interest", "desire"):
                if has_product:
                    score += 0.3
                else:
                    score -= 0.2

            # Repetition penalty
            score -= seg["used_count"] * 0.25

            # Adjacency penalty: avoid same segment twice in a row
            if seg["index"] == prev_seg_index:
                score -= 0.3

            ranked.append({"segment": seg, "score": score})

        ranked.sort(key=lambda x: x["score"], reverse=True)

        winner = ranked[0]["segment"]
        winner["used_count"] += 1
        prev_seg_index = winner["index"]

        best_cuts.append({
            "segment_index": winner["index"],
            "duration": slot["duration"],
            "score": round(ranked[0]["score"], 3),
        })
        logger.warning(
            f"[MATCH] Slot {slot_idx} [{slot['start']:.1f}-{slot['end']:.1f}s] "
            f"({aida_phase}) -> Segment {winner['index']} "
            f"(Score: {ranked[0]['score']:.3f}) "
            f"desc: {winner.get('description', '')[:60]}..."
        )

    # 5. Build output clips with correct keys for tasks.py
    segment_playheads = {}
    selected_clips = []
    clip_order = 0

    for cut in best_cuts:
        idx = cut["segment_index"]
        required_duration = float(cut["duration"])

        if idx not in segment_playheads:
            segment_playheads[idx] = float(segments[idx].get("start_sec", 0.0))

        seg = segments[idx]
        seg_id = str(seg["id"])

        available = float(seg.get("end_sec", required_duration)) - segment_playheads[idx]

        if available >= required_duration:
            selected_clips.append({
                "id": seg_id,
                "start_sec": segment_playheads[idx],
                "end_sec": segment_playheads[idx] + required_duration,
                "order": clip_order,
            })
            segment_playheads[idx] += required_duration
            clip_order += 1
        else:
            # Cascading: chain multiple segments to fill the slot.
            # When all footage is exhausted, loop from the beginning of all segments.
            remaining_dur = required_duration
            curr_idx = idx
            exhausted_count = 0

            while remaining_dur > 0.05:
                if exhausted_count >= len(segments):
                    # All segments exhausted — reset all playheads and start over (loop)
                    for i in range(len(segments)):
                        segment_playheads[i] = float(segments[i].get("start_sec", 0.0))
                    exhausted_count = 0

                s = segments[curr_idx]
                if curr_idx not in segment_playheads:
                    segment_playheads[curr_idx] = float(s.get("start_sec", 0.0))

                avail = float(s.get("end_sec", remaining_dur)) - segment_playheads[curr_idx]

                if avail > 0.1:
                    chunk = min(avail, remaining_dur)
                    selected_clips.append({
                        "id": str(s["id"]),
                        "start_sec": segment_playheads[curr_idx],
                        "end_sec": segment_playheads[curr_idx] + chunk,
                        "order": clip_order,
                    })
                    segment_playheads[curr_idx] += chunk
                    remaining_dur -= chunk
                    clip_order += 1
                else:
                    # This segment is exhausted, move to next without resetting its playhead
                    exhausted_count += 1
                    curr_idx = (curr_idx + 1) % len(segments)
                    if curr_idx not in segment_playheads:
                        segment_playheads[curr_idx] = float(segments[curr_idx].get("start_sec", 0.0))

    logger.warning(f"[MATCH] Generated {len(selected_clips)} clips for FFmpeg stitching.")
    return selected_clips
