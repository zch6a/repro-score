# Sparse Mixers for Small Images

Code for the made-up paper *Sparse Mixers for Small Images* (repro-score's example: the method, the numbers and the
authors do not exist).

## Setup

```bash
pip install -r requirements.txt
```

## Training

```bash
python train.py --config configs/cifar10.yaml
python train.py --config configs/cifar100.yaml
```

## Evaluation

```bash
python eval.py --checkpoint runs/cifar10/best.pt
bash scripts/eval_all.sh
```

## Results

| Dataset | Top-1 (%) | Params (M) |
|---|---|---|
| CIFAR-10 | 94.1 | 4.2 |
| CIFAR-100 | 76.8 | 4.3 |

The datasets, CIFAR-10 and CIFAR-100, are downloaded by torchvision the first time `train.py` runs (see
https://www.cs.toronto.edu/~kriz/cifar.html).

Each run trains a sparse mixer from scratch with the hyperparameters in `configs/`; the numbers above are the mean of
the runs in our paper. The mixer layers replace attention with sparse token mixing, so the model is small enough to
train on one GPU, and the evaluation script reports top-1 accuracy on the test split.
