# Fine-Tuning Pipeline (Optional)

This directory contains scripts to fine-tune a base LLM on your insurance domain data.

## When to Use Fine-Tuning vs RAG

| | RAG | Fine-Tuning |
|---|---|---|
| Adding new knowledge | Upload a document | Requires retraining |
| Response style | Unchanged base model | Customizable |
| Cost | Zero (just embed+store) | GPU hours |
| Best for | Factual Q&A from docs | Style/persona/reasoning |

**For most insurance chatbot use cases, RAG is sufficient.** Fine-tune only if you need the model to reason in a specific way or adopt a brand voice.

## Quick Start (LoRA Fine-Tuning with Mistral 7B)

### Requirements
- Python 3.11+
- NVIDIA GPU with 16GB+ VRAM (or use Google Colab Pro)
- `pip install transformers peft datasets bitsandbytes trl`

### Steps

1. **Prepare dataset** (`data/training_data.jsonl`):
```json
{"prompt": "What is NCD in Sri Lanka?", "completion": "NCD stands for No-Claim Discount..."}
{"prompt": "How do I file a health insurance claim?", "completion": "To file a health claim..."}
```

2. **Run training** (`python train_lora.py`)
3. **Merge adapters** (`python merge_adapters.py`)
4. **Convert to GGUF** for Ollama (`./convert_to_gguf.sh`)
5. **Register in Ollama** (`ollama create insurance-bot -f Modelfile`)

## Modelfile for Custom Model

```
FROM ./insurance-mistral-q4.gguf
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
SYSTEM "You are InsurBot, an insurance specialist assistant..."
```
