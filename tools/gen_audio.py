"""Generate Azure neural audio + word timings for every question segment.
Incremental: a clip is regenerated only if its spoken text changed.
Env: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, VOICE (default en-US-SaraNeural)."""
import hashlib, json, os, pathlib, re, sys, threading
from concurrent.futures import ThreadPoolExecutor
import azure.cognitiveservices.speech as sdk

VOICE = os.environ.get("VOICE", "en-US-SaraNeural")
SLUG = VOICE.replace("en-US-", "").replace("Neural", "").lower()
OUT = pathlib.Path("audio") / SLUG
OUT.mkdir(parents=True, exist_ok=True)
MAN = OUT / "timings.json"
man = json.load(open(MAN)) if MAN.exists() else {"voice": VOICE, "clips": {}}

MAP = {"mph": "miles per hour", "ft": "feet", "p.": "page", "pp.": "pages", "vs": "versus", "vs.": "versus", "&": "and",
       "DMV": "D M V", "GDL": "G D L", "HOV": "H O V", "IID": "I I D", "RR": "R R", "EMS": "E M S", "U-turn": "U turn", "U-turns": "U turns"}
def spoken(w):  # must mirror spoken() in index.html
    core = re.sub(r'^[("\'“]+|[)"\'”,.;:!?]+$', "", w)
    if core in MAP: return w.replace(core, MAP[core], 1)
    if re.match(r"^p\.\d", core): return re.sub(r"^p\.", "page ", w)
    w = re.sub(r"(\d+)%", r"\1 percent", w); w = re.sub(r"^\.(\d)", r"point \1", w)
    w = re.sub(r"(\d)/(\d)", r"\1 \2", w); w = w.replace("/", " "); w = re.sub("–|—", " to ", w)
    return w

def plan():
    data = json.load(open("questions.json"))["questions"]
    if os.environ.get("LIMIT"): data = data[:int(os.environ["LIMIT"])]
    jobs = {}
    for L in "ABCD":
        jobs[f"_intro/ans{L}"] = (f"Answer {L}", None)
        jobs[f"_intro/wrong{L}"] = (f"Answer {L} is wrong", None)
        jobs[f"_intro/right{L}"] = (f"The right answer is {L}", None)
    for q in data:
        segs = {"q": q["q"], "why": q.get("why") or q["ref"]}
        for i, o in enumerate(q["options"]): segs[f"o{i}"] = o
        for i, w in enumerate(q.get("wrong") or []):
            if w: segs[f"x{i}"] = w
        for k, txt in segs.items():
            jobs[f"{q['id']}/{k}"] = (None, txt)
    return jobs

def build_text(intro, display):
    if intro is not None: return intro, []
    words = [t for t in re.split(r"\s+", display) if t]
    text, starts = "", []
    for w in words:
        if text: text += " "
        starts.append(len(text)); text += spoken(w)
    return text, starts

cfg = sdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"])
cfg.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3)
cfg.speech_synthesis_voice_name = VOICE
lock = threading.Lock(); chars = [0]; fails = []

def run(key, intro, display):
    text, starts = build_text(intro, display)
    h = hashlib.sha1((VOICE + "|" + text).encode()).hexdigest()[:12]
    path = OUT / f"{key}.mp3"
    if man["clips"].get(key, {}).get("h") == h and path.exists(): return
    path.parent.mkdir(parents=True, exist_ok=True)
    bounds = []
    for attempt in range(4):
        bounds.clear()
        synth = sdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
        def wb(evt):
            if evt.boundary_type == sdk.SpeechSynthesisBoundaryType.Word:
                bounds.append((round(evt.audio_offset / 10000), evt.text_offset))
        synth.synthesis_word_boundary.connect(wb)
        r = synth.speak_text_async(text).get()
        if r.reason == sdk.ResultReason.SynthesizingAudioCompleted: break
    else:
        fails.append(key); return
    path.write_bytes(r.audio_data)
    # map text offsets -> display word index
    t = []
    for ms, off in bounds:
        k = -1
        for j, s in enumerate(starts):
            if s <= off: k = j
            else: break
        if k >= 0 and (not t or t[-1][1] != k): t.append([ms, k])
    with lock:
        man["clips"][key] = {"h": h, "t": t, "d": round(r.audio_duration.total_seconds() * 1000)}
        chars[0] += len(text)

jobs = plan()
keys = sorted(jobs)
# drop clips that no longer exist (full runs only)
for k in ([] if os.environ.get("LIMIT") else list(man["clips"])):
    if k not in jobs:
        man["clips"].pop(k); p = OUT / f"{k}.mp3"
        if p.exists(): p.unlink()
with ThreadPoolExecutor(8) as ex:
    for k in keys: ex.submit(run, k, *jobs[k])
man["voice"] = VOICE
json.dump(man, open(MAN, "w"), separators=(",", ":"))
print("clips:", len(man["clips"]), "new chars billed:", chars[0], "failures:", len(fails), fails[:10])
if fails: sys.exit(1)
