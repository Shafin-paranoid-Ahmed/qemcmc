"""Clean-evaluation metrics for the Full-QCNN Phase-A pilot."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, log_loss, recall_score


def ece_15bin(probs, labels):
    probs, labels = np.asarray(probs, float), np.asarray(labels, int)
    confidence, prediction = probs.max(1), probs.argmax(1)
    value = 0.0
    for index in range(15):
        low, high = index / 15, (index + 1) / 15
        mask = (confidence >= low) & (confidence < high if index < 14 else confidence <= high)
        if mask.any():
            value += mask.mean() * abs((prediction[mask] == labels[mask]).mean() - confidence[mask].mean())
    return float(value)


def macro_f1(preds, labels):
    return float(f1_score(labels, preds, average="macro", zero_division=0))


def classification_metrics(probs, labels, class_names=None, calibration_probs=None):
    probs, labels = np.asarray(probs, float), np.asarray(labels, int)
    probs = np.clip(probs, 1e-12, None)
    probs = probs / probs.sum(axis=1, keepdims=True)
    calibration_probs = probs if calibration_probs is None else np.asarray(calibration_probs, float)
    calibration_probs = np.clip(calibration_probs, 1e-12, None)
    calibration_probs = calibration_probs / calibration_probs.sum(axis=1, keepdims=True)
    pred = probs.argmax(1)
    n_classes = probs.shape[1]
    recall = recall_score(labels, pred, labels=np.arange(n_classes), average=None, zero_division=0)
    one_hot = np.eye(n_classes)[labels]
    return {
        "accuracy": float(accuracy_score(labels, pred)),
        "macro_f1": macro_f1(pred, labels),
        "macro_recall": float(recall_score(labels, pred, average="macro", zero_division=0)),
        "ece_15bin": ece_15bin(calibration_probs, labels),
        "brier": float(np.mean(np.sum((calibration_probs - one_hot) ** 2, axis=1))),
        "nll": float(log_loss(labels, calibration_probs, labels=np.arange(n_classes))),
        "per_class_recall": {str(class_names[i] if class_names else i): float(recall[i]) for i in range(n_classes)},
    }
