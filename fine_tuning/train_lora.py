"""
LoRA Fine-Tuning Script for Insurance Chatbot
Tested with: Mistral-7B-Instruct-v0.3
Hardware: ~16GB VRAM (or Google Colab A100)

Run: python train_lora.py
"""
import json
import os
from dataclasses import dataclass


@dataclass
class TrainingConfig:
    base_model: str = "mistralai/Mistral-7B-Instruct-v0.3"
    dataset_path: str = "data/training_data.jsonl"
    output_dir: str = "./outputs/insurance-lora"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    max_seq_length: int = 2048
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    load_in_4bit: bool = True


def load_dataset(path: str):
    """Load JSONL training data with prompt/completion pairs."""
    examples = []
    with open(path) as f:
        for line in f:
            item = json.loads(line.strip())
            # Format as instruction-following
            text = f"<s>[INST] {item['prompt']} [/INST] {item['completion']}</s>"
            examples.append({"text": text})
    return examples


def train(cfg: TrainingConfig):
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from trl import SFTTrainer
        from datasets import Dataset
    except ImportError:
        print("Install: pip install transformers peft datasets bitsandbytes trl")
        return

    # 4-bit quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=cfg.load_in_4bit,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    print(f"Loading base model: {cfg.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # LoRA config
    lora_config = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=cfg.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load data
    print(f"Loading dataset: {cfg.dataset_path}")
    examples = load_dataset(cfg.dataset_path)
    dataset = Dataset.from_list(examples)

    # Training arguments
    training_args = TrainingArguments(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.num_train_epochs,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        learning_rate=cfg.learning_rate,
        fp16=True,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=cfg.max_seq_length,
    )

    print("Starting fine-tuning...")
    trainer.train()
    trainer.save_model(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)
    print(f"Model saved to: {cfg.output_dir}")
    print("Next: run merge_adapters.py, then convert to GGUF for Ollama.")


if __name__ == "__main__":
    cfg = TrainingConfig()
    train(cfg)
