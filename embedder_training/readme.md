# Reranker Model Training

This repository contains code for training reranker models using ModernBERT and question-answer similarity objectives for our Tübingen-Focused Web Search System.

## Embedder Model
- **Base Architecture**: `ModernBERT-base` from Hugging Face
  - Model: [`answerdotai/ModernBERT-base`](https://huggingface.co/answerdotai/ModernBERT-base)
- **Purpose**: Fine-tuned for reranking tasks using similarity learning
- Added trainable dense projection layers on top of BERT outputs

## Dataset
- **Source**: `gooaq` from Sentence-Transformers
  - [Dataset Card](https://huggingface.co/datasets/sentence-transformers/gooaq)
- **Content**: 3.4M Google-derived question-answer pairs

## Training Details
- Used Cosine similarity objective
- Added classifier head
- Released trained model to [as-bessonov/reranker_searchengines_cos2](https://huggingface.co/as-bessonov/reranker_searchengines_cos2)
