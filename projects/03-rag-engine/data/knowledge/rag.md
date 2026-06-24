# Retrieval-Augmented Generation (RAG)

RAG combines a retrieval step with a generation step. Instead of relying only on the
model's parametric memory, the system first retrieves relevant documents and then asks the
language model to answer using that retrieved context.

## Why RAG

Large language models can hallucinate facts. By grounding answers in retrieved source
text, RAG reduces hallucinations and lets you answer questions about private or recent data
the base model never saw during training.

## The pipeline

1. **Ingestion** - documents are split into chunks, embedded into vectors, and stored.
2. **Retrieval** - the user question is embedded and the most similar chunks are fetched.
3. **Generation** - the chunks are inserted into a prompt and the model answers from them.

## Chunking

Chunk size is a trade-off. Small chunks improve retrieval precision but can lose context;
large chunks keep context but dilute relevance. This project uses a chunk size of 800
characters with 120 characters of overlap so ideas that span a boundary are not lost.

## Faithfulness

A faithful answer is one fully supported by the retrieved context. The pipeline prompt
instructs the model to answer only from context and to reply that it lacks information when
the context is insufficient, rather than guessing.
