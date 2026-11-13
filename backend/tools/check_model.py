"""S0 : le modèle se charge-t-il depuis le disque et répond-il ? Mesure RAM et latence CPU.

Usage : python tools/check_model.py [--model models/nllb_ff] [--data languages/ff/check_model.json]
Aucun accès réseau : HF_HUB_OFFLINE est forcé. Une différence avec Colab se signale, elle ne se corrige pas.
"""
import argparse
import json
import math
import os
import resource
import statistics
import time

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # Linux : ko


def translate(tok, model, texts, beams=4):
    tok.src_lang = "fra_Latn"
    enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=128)
    with torch.inference_mode():
        out = model.generate(
            **enc,
            forced_bos_token_id=tok.convert_tokens_to_ids("fuv_Latn"),
            num_beams=beams,
            max_new_tokens=96,
            output_scores=True,
            return_dict_in_generate=True,
        )
    texts_out = tok.batch_decode(out.sequences, skip_special_tokens=True)
    return [(t, math.exp(s)) for t, s in zip(texts_out, out.sequences_scores.tolist())]


def timed(tok, model, texts, runs=3):
    durations = []
    for _ in range(runs):
        t0 = time.perf_counter()
        translate(tok, model, texts)
        durations.append(time.perf_counter() - t0)
    return statistics.median(durations), max(durations)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("AMIRA_MODEL_DIR", "models/nllb_ff"))
    ap.add_argument("--data", default=f"languages/{os.environ.get('AMIRA_LANGUAGE', 'ff')}/check_model.json")
    args = ap.parse_args()
    data = json.load(open(args.data, encoding="utf-8"))

    print(f"torch {torch.__version__}, {torch.get_num_threads()} fils CPU, RSS départ {rss_mb():.0f} Mo")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model).eval()
    print(f"chargement {time.perf_counter() - t0:.1f} s, RSS max {rss_mb():.0f} Mo")

    ctrl = data["control"]
    (got, conf), = translate(tok, model, [ctrl["source"]])
    verdict = "IDENTIQUE à Colab" if got == ctrl["colab"] else f"DIFFÉRENT de Colab (attendu : {ctrl['colab']!r})"
    print(f"\ncontrôle : {ctrl['source']!r} → {got!r} conf {conf:.2f} : {verdict}\n")

    for src in data["sentences"]:
        t1 = time.perf_counter()
        (out, conf), = translate(tok, model, [src])
        print(f"{time.perf_counter() - t1:5.2f} s  conf {conf:.2f}  {src!r}\n        → {out!r}")

    one = timed(tok, model, data["sentences"][:1])
    eight = timed(tok, model, (data["sentences"] * 2)[:8])
    print(f"\n1 segment  : médiane {one[0]:.2f} s, max {one[1]:.2f} s (3 essais)")
    print(f"8 segments : médiane {eight[0]:.2f} s, max {eight[1]:.2f} s (3 essais)")
    print(f"RSS max du processus : {rss_mb():.0f} Mo")


if __name__ == "__main__":
    main()
