"""Generate short Azure neural voice samples so a voice can be picked by ear.
Needs env AZURE_SPEECH_KEY and AZURE_SPEECH_REGION (GitHub secrets)."""
import json, os, pathlib
import azure.cognitiveservices.speech as sdk

VOICES = [
    "en-US-AvaMultilingualNeural", "en-US-EmmaMultilingualNeural", "en-US-AndrewMultilingualNeural",
    "en-US-BrianMultilingualNeural", "en-US-JennyNeural", "en-US-AriaNeural", "en-US-AvaNeural",
    "en-US-EmmaNeural", "en-US-SaraNeural", "en-US-MichelleNeural", "en-US-GuyNeural", "en-US-ChristopherNeural",
]
TEXT = ("You are driving at night and an oncoming motorcycle approaches. Why does the manual tell you to dim your headlights? "
        "Answer A. High beams can blind a motorcyclist, which is far more dangerous for them than for other drivers.")
out = pathlib.Path("audio/samples"); out.mkdir(parents=True, exist_ok=True)
cfg = sdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"], region=os.environ["AZURE_SPEECH_REGION"])
cfg.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3)
done = []
for v in VOICES:
    cfg.speech_synthesis_voice_name = v
    synth = sdk.SpeechSynthesizer(speech_config=cfg, audio_config=sdk.audio.AudioOutputConfig(filename=str(out / f"{v}.mp3")))
    r = synth.speak_text_async(TEXT).get()
    if r.reason == sdk.ResultReason.SynthesizingAudioCompleted:
        done.append(v); print("ok", v)
    else:
        print("FAILED", v, r.reason, getattr(r, "cancellation_details", None) and r.cancellation_details.error_details)
json.dump(done, open(out / "voices.json", "w"))
