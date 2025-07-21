import logging
import traceback

import torch
from datasets import load_dataset
from datasets import Dataset
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import (
    CrossEncoder,
    CrossEncoderModelCardData,
    CrossEncoderTrainer,
    CrossEncoderTrainingArguments,
)
from sentence_transformers.cross_encoder.evaluation import (
    CrossEncoderNanoBEIREvaluator,
    CrossEncoderRerankingEvaluator,
)
from sentence_transformers.cross_encoder.losses.BinaryCrossEntropyLoss import BinaryCrossEntropyLoss
from sentence_transformers.evaluation.SequentialEvaluator import SequentialEvaluator
from sentence_transformers.util import mine_hard_negatives
from sentence_transformers import SentenceTransformer, InputExample, losses
from sentence_transformers.training_args import SentenceTransformerTrainingArguments
from sentence_transformers.trainer import SentenceTransformerTrainer
from sentence_transformers.evaluation import RerankingEvaluator
import torch.nn as nn

logging.basicConfig(format="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)


model_name = "answerdotai/ModernBERT-base" # Fine general model

train_batch_size = 256 # Better to increase on 80GB cards
num_epochs = 1 # 2 are also fine, but takes more time
num_hard_negatives = 5  # How many hard negatives should be mined for each question-answer pair



# Load the GooAQ dataset: https://huggingface.co/datasets/sentence-transformers/gooaq
logging.info("Read the gooaq training dataset")
full_dataset = load_dataset("sentence-transformers/gooaq", split="train").select(range(3012496))
dataset_dict = full_dataset.train_test_split(test_size=1_000, seed=12)
train_dataset = dataset_dict["train"]
eval_dataset = dataset_dict["test"]
logging.info(train_dataset)
logging.info(eval_dataset)

# Modify training dataset to include hard negatives using a ready-to-use embedding model
embedding_model = SentenceTransformer("sentence-transformers/static-retrieval-mrl-en-v1", device="cuda")
hard_train_dataset = mine_hard_negatives( # Will find us hardest (i.e. most close to gt) samples in dataset
    train_dataset, # Dataset to mine from
    embedding_model, # This will be used to find hard negatives
    num_negatives=num_hard_negatives,  # How many negatives per question-answer pair
    margin=0,
    range_min=0,
    range_max=100,
    sampling_strategy="top",  # Sample the top negatives from the range
    batch_size=4096,  # Use a batch size of 4096 for the embedding model
    output_format="labeled-pair",  # The output format is (query, passage, label), as required by BinaryCrossEntropyLoss
    use_faiss=True, # Just to improve mining efficiency
)
logging.info(hard_train_dataset)



# Initialize embedder model with BERT
model = SentenceTransformer(model_name)

# Convert initial dataset to InputExamples for bi-encoder training
def convert_triplet_to_pairs(dataset):
    questions = []
    sentences = []
    labels = []
    
    for sample in dataset:
        assert sample['label'] in {0,1}, f"Sample label {sample['label']}"
        if sample['label'] == 1: # It's relevant pair
            questions.append(sample['question'])  # question
            sentences.append(sample['answer'])  # correct answer
            labels.append(1.0)
        else:
            # Negative pair
            questions.append(sample['question'])  # same question
            sentences.append(sample['answer'])  # wrong answer
            labels.append(0.0)
    
    return Dataset.from_dict({
        'sentence1': questions,
        'sentence2': sentences,
        'label': labels
    })

train_examples = convert_triplet_to_pairs(hard_train_dataset)
loss = losses.CosineSimilarityLoss(model) # We train with cosine similarity

run_name = f"2cosine-reranker-mbert-gooaq-bce"
args = SentenceTransformerTrainingArguments(
    output_dir=f"models/{run_name}",
    num_train_epochs=num_epochs,
    per_device_train_batch_size=train_batch_size,
    learning_rate=2e-5,
    warmup_ratio=0.1,
    fp16=False,
    bf16=True,
    dataloader_num_workers=4,
    # eval_strategy="steps", # May uncomment for validation (but need to provide eval then)
    # eval_steps=4000,
    save_strategy="steps",
    save_steps=4000,
    logging_steps=10,
    run_name=run_name,
    seed=1984, # George Orwell's seed
)

# Create trainer
trainer = SentenceTransformerTrainer(
    model=model,
    args=args,
    train_dataset=train_examples,
    loss=loss,
)

trainer.train()
# Save the final model (I also pushed it to HF)
final_output_dir = f"models/final"
model.save_pretrained(final_output_dir)
