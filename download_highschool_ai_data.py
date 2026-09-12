from datasets import load_dataset
from pathlib import Path

# Storage location (relative to this script, so it always lands in the repo)
SAVE_FOLDER = Path(__file__).resolve().parent / "HighSchool_Study_AI_Datasets"
SAVE_FOLDER.mkdir(exist_ok=True)


datasets = {
    # Math reasoning
    "GSM8K_Math": {
        "dataset": "openai/gsm8k",
        "config": "main"
    },

    # General high school subjects
    "MMLU_HighSchool": {
        "dataset": "cais/mmlu",
        "config": "all"
    },

    # Science questions
    "SciQ_Science": {
        "dataset": "allenai/sciq",
        "config": None
    },

    # Science reasoning
    "ARC_Science": {
        "dataset": "allenai/ai2_arc",
        "config": "ARC-Challenge"
    },

    # Reading comprehension
    "SQuAD_Reading": {
        "dataset": "rajpurkar/squad",
        "config": None
    },

    # Teacher-style conversations
    "OpenAssistant_Tutoring": {
        "dataset": "OpenAssistant/oasst1",
        "config": None
    }
}


def download_dataset(name, info):

    print("\n==============================")
    print("Downloading:", name)
    print("==============================")

    try:
        if info["config"]:
            data = load_dataset(
                info["dataset"],
                info["config"]
            )
        else:
            data = load_dataset(
                info["dataset"]
            )

        save_path = SAVE_FOLDER / name

        data.save_to_disk(
            str(save_path)
        )

        print("Saved:", save_path)

    except Exception as e:
        print("ERROR:", name)
        print(e)


for name, info in datasets.items():
    download_dataset(name, info)

print("\nDONE!")
print("Location:", SAVE_FOLDER)
