from musicquiz.models import Question


def get_question_media(question: Question):
    if question.type == "video":
        video = question.video
        if not video:
            return {"url": "", "start": 0.0}
        return {"url": f"/stream_video/{video.filename}", "start": video.start_time or 0.0}

    if question.type in ["audio", "simultaneous"]:
        audio = question.song if question.type == "audio" else question.simultaneous
        if not audio:
            return {"url": "", "start": 0.0}
        return {"url": f"/stream_song/{audio.filename}", "start": audio.start_time or 0.0}

    return {"url": "", "start": 0.0}


def get_question_display(question: Question):
    base = {
        "id": question.id,
        "type": question.type,
        "round": question.round_number,
        "round_number": question.round_number,
        "order": question.position or 1,
        "song_position": question.position or 1,
        "duration": float(question.duration or 0),
    }

    if question.type == "audio" and question.song:
        base.update({
            "artist": question.song.artist,
            "title": question.song.title,
            "filename": question.song.filename,
            "start": float(question.song.start_time or 0),
            "start_time": float(question.song.start_time or 0),
        })
        return base

    if question.type == "video" and question.video:
        base.update({
            "artist": question.video.artist,
            "title": question.video.title,
            "filename": question.video.filename,
            "start": float(question.video.start_time or 0),
            "start_time": float(question.video.start_time or 0),
        })
        return base

    if question.type == "simultaneous" and question.simultaneous:
        base.update({
            "artist": question.simultaneous.artist,
            "title": question.simultaneous.title,
            "filename": question.simultaneous.filename,
            "start": float(question.simultaneous.start_time or 0),
            "start_time": float(question.simultaneous.start_time or 0),
            "extra_question": question.simultaneous.extra_question,
        })
        return base

    if question.type == "text" and question.text:
        base.update({
            "artist": "Text Question",
            "title": (question.text.question_text or "")[:50],
            "question_text": question.text.question_text or "",
        })
        return base

    if question.type == "text_multiple" and question.text_multiple:
        base.update({
            "artist": "Multiple Choice",
            "title": (question.text_multiple.question_text or "")[:50],
            "question_text": question.text_multiple.question_text or "",
            "choices": question.text_multiple.get_choices(),
            "correct_index": int(question.text_multiple.correct_index or 0),
        })
        return base

    return base


def get_question_unlock_payload(question: Question):
    payload = {
        "question_id": question.id,
        "question_index": question.position or 1,
        "round": question.round_number,
        "question_type": question.type,
        "question_text": "",
        "extra_question": "",
        "choices": [],
    }

    if question.type == "text" and question.text:
        payload["question_text"] = question.text.question_text or ""

    if question.type == "text_multiple" and question.text_multiple:
        payload["question_text"] = question.text_multiple.question_text or ""
        payload["choices"] = question.text_multiple.get_choices()

    if question.type == "simultaneous" and question.simultaneous:
        payload["extra_question"] = question.simultaneous.extra_question or ""

    return payload


def get_question_answer_key(question: Question):
    if question.type == "audio" and question.song:
        return {
            "artist": question.song.artist,
            "title": question.song.title,
            "extra": "",
            "choice": "",
        }

    if question.type == "video" and question.video:
        return {
            "artist": question.video.artist,
            "title": question.video.title,
            "extra": "",
            "choice": "",
        }

    if question.type == "text" and question.text:
        return {
            "artist": "",
            "title": question.text.answer_text or question.text.question_text or "",
            "extra": "",
            "choice": "",
        }

    if question.type == "text_multiple" and question.text_multiple:
        correct_idx = int(question.text_multiple.correct_index or 0)
        choices = question.text_multiple.get_choices()
        correct_choice = choices[correct_idx] if 0 <= correct_idx < len(choices) else ""
        return {
            "artist": "",
            "title": "",
            "extra": "",
            "choice": correct_choice,
        }

    if question.type == "simultaneous" and question.simultaneous:
        return {
            "artist": question.simultaneous.artist,
            "title": question.simultaneous.title,
            "extra": question.simultaneous.extra_answer or "",
            "choice": "",
        }

    return {"artist": "", "title": "", "extra": "", "choice": ""}
