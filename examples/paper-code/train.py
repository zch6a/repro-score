"""Trains a sparse mixer (repro-score's made-up example)."""

import argparse
import random

import numpy as np
import torch


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/cifar10.yaml")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)


if __name__ == "__main__":
    main()
