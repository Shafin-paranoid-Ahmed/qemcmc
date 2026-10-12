from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader, Dataset
from torchvision.models import ResNet18_Weights, resnet18

from common import RESULTS, DATA_ROOT, load_split, seed_all, write_json, write_rows


class Images(Dataset):
    def __init__(self, ids: list[str], transform):
        self.ids, self.transform = ids, transform

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, index):
        image_id = self.ids[index]
        path = DATA_ROOT / "test" / image_id / f"{image_id}.jpg"
        with Image.open(path) as image:
            return self.transform(image.convert("RGB")), image_id


@torch.inference_mode()
def extract(ids: list[str], batch_size: int) -> tuple[np.ndarray, float, str]:
    weights = ResNet18_Weights.IMAGENET1K_V1
    model = resnet18(weights=weights)
    model.fc = torch.nn.Identity()
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    loader = DataLoader(Images(ids, weights.transforms()), batch_size=batch_size,
                        shuffle=False, num_workers=0, pin_memory=device.type == "cuda")
    started = time.perf_counter()
    chunks = [model(images.to(device, non_blocking=True)).cpu().numpy() for images, _ in loader]
    return np.concatenate(chunks), time.perf_counter() - started, str(device)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument(
        "--bits", type=int, default=20, choices=(*range(1, 21), 22, 24)
    )
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--tag", default=None)
    parser.add_argument(
        "--retag-existing",
        action="store_true",
        help="Create a new tagged exact copy of existing same-width artifacts without re-extracting the frozen encoder.",
    )
    args = parser.parse_args()
    if args.retag_existing:
        if not args.tag:
            raise ValueError("--retag-existing requires --tag")
        quality_rows = []
        for seed in args.seeds:
            source_csv = RESULTS / f"codes_frozenresnet_level-c_{seed}_codes.csv"
            source_metadata = RESULTS / f"codes_frozenresnet_level-c_{seed}_metadata.json"
            with source_csv.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            manifest = load_split(seed)
            expected_partition = {
                image_id: partition
                for partition in ("train", "val", "test")
                for image_id in manifest[partition]
            }
            observed_ids = {row["image_id"] for row in rows}
            if observed_ids != set(expected_partition):
                raise RuntimeError(f"source IDs do not match trusted split for seed {seed}")
            if any(
                row["partition"] != expected_partition[row["image_id"]]
                or int(row["label"]) != int(manifest["label_map"][row["image_id"]])
                for row in rows
            ):
                raise RuntimeError(f"source partition/label mismatch for seed {seed}")
            bit_names = [name for name in rows[0] if name.startswith("bit_")]
            if len(bit_names) != args.bits:
                raise RuntimeError(
                    f"source seed {seed} has {len(bit_names)} bits, requested {args.bits}"
                )
            metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
            if int(metadata["bits"]) != args.bits:
                raise RuntimeError(f"source metadata width mismatch for seed {seed}")
            target = f"codes_frozenresnet_level-c_{seed}_{args.tag}"
            write_rows(RESULTS / f"{target}_codes.csv", rows)
            write_json(RESULTS / f"{target}_metadata.json", {
                **metadata,
                "source_artifact": source_csv.name,
                "retagged_exact_copy": True,
                "pca_fit_partition": "trusted train partition in source build",
                "trusted_split_membership_validated": True,
            })
            quality_rows.append({key: metadata[key] for key in (
                "seed", "bits", "val_macro_f1", "val_accuracy",
                "majority_accuracy", "pca_explained_variance",
            )})
        write_rows(
            RESULTS / f"codes_frozenresnet_level-c_all_{args.tag}_quality.csv",
            quality_rows,
        )
        write_json(
            RESULTS / f"codes_frozenresnet_level-c_all_{args.tag}_timing.json",
            {
                "retagged_exact_copy": True,
                "source": "existing untagged 20-bit G1 artifacts",
                "feature_seconds": 0.0,
                "device": "not rerun; frozen source artifacts reused",
            },
        )
        print(f"Retagged exact {args.bits}-bit Level-C copies for {args.seeds}")
        return
    seed_all(0)
    manifests = {seed: load_split(seed) for seed in args.seeds}
    all_ids = sorted(set().union(*(m[part] for m in manifests.values() for part in ("train", "val", "test"))))
    features, seconds, device = extract(all_ids, args.batch_size)
    feature_by_id = dict(zip(all_ids, features))
    quality_rows = []
    for seed, manifest in manifests.items():
        ordered = [(image_id, part) for part in ("train", "val", "test") for image_id in manifest[part]]
        train_features = np.stack([feature_by_id[i] for i in manifest["train"]])
        pca = PCA(n_components=args.bits, random_state=seed).fit(train_features)
        projected = pca.transform(np.stack([feature_by_id[i] for i, _ in ordered]))
        # Sign threshold is the zero point of train-centered PCA coordinates.
        codes = (projected >= 0.0).astype(np.int8)
        rows = []
        for (image_id, part), code in zip(ordered, codes):
            row = {"image_id": image_id, "partition": part, "label": manifest["label_map"][image_id]}
            row.update({f"bit_{i}": int(value) for i, value in enumerate(code)})
            rows.append(row)
        suffix = f"_{args.tag}" if args.tag else ""
        tag = f"codes_frozenresnet_level-c_{seed}{suffix}"
        write_rows(RESULTS / f"{tag}_codes.csv", rows)
        train_mask = np.array([part == "train" for _, part in ordered])
        val_mask = np.array([part == "val" for _, part in ordered])
        labels = np.array([manifest["label_map"][i] for i, _ in ordered])
        head = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed).fit(codes[train_mask], labels[train_mask])
        pred = head.predict(codes[val_mask])
        majority = np.bincount(labels[train_mask]).argmax()
        majority_pred = np.full(val_mask.sum(), majority)
        quality = {
            "seed": seed,
            "bits": args.bits,
            "val_macro_f1": float(f1_score(labels[val_mask], pred, average="macro")),
            "val_accuracy": float(accuracy_score(labels[val_mask], pred)),
            "majority_accuracy": float(np.mean(labels[val_mask] == majority)),
            "majority_macro_f1": float(f1_score(labels[val_mask], majority_pred, average="macro", zero_division=0)),
            "pca_explained_variance": float(pca.explained_variance_ratio_.sum()),
        }
        quality_rows.append(quality)
        write_json(RESULTS / f"{tag}_metadata.json", {**quality, "encoder": "ResNet18_Weights.IMAGENET1K_V1", "threshold": "train-centered PCA zero", "encoder_frozen": True})
    suffix = f"_{args.tag}" if args.tag else ""
    write_rows(RESULTS / f"codes_frozenresnet_level-c_all{suffix}_quality.csv", quality_rows)
    write_json(RESULTS / f"codes_frozenresnet_level-c_all{suffix}_timing.json", {"unique_images": len(all_ids), "feature_seconds": seconds, "device": device})
    print(quality_rows)


if __name__ == "__main__":
    main()
