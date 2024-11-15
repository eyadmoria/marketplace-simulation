import argparse
import os
import pickle

from pathlib import Path
from typing import Dict

import hyperopt.hp as hp
import mlflow
import sbi.utils as sbi_utils
import torch

from hyperopt import STATUS_FAIL, STATUS_OK, Trials, fmin, tpe
from snpe.inference.inference_class import TimeSeriesInference

# LOCAL_ARTIFACT_PATH = Path("./artifacts/hyperparameter_tuning/cnn_tuning")
# GCS_ARTIFACT_PATH = Path("../../gcs_mount/artifacts/double_herding_simulator")
LOCAL_ARTIFACT_PATH = Path("./artifacts/rating_spacing_simulator")
GCS_ARTIFACT_PATH = Path("../../gcs_mount/artifacts/rating_spacing_simulator")


SEARCH_SPACE = {
    "batch_size": hp.choice("batch_size", [32, 64, 128, 256]),
    # log(1e-6)=-13.82, log(1e-2)=-4.6, as a result learning rate is log-uniform distributed between
    # 1e-6 and 1e-2 in the setup below
    # "learning_rate": hp.loguniform("learning_rate", -13.82, -4.6),
    "learning_rate": hp.uniform("learning_rate", 1e-6, 5e-1),
    "hidden_features": hp.choice("hidden_features", range(20, 80, 5)),
    "num_transforms": hp.choice("num_transforms", range(2, 9, 1)),
    "num_conv_layers": hp.choice("num_conv_layers", range(1, 7, 1)),
    "num_channels": hp.choice("num_channels", range(3, 16, 1)),
    "conv_kernel_size": hp.choice("conv_kernel_size", range(3, 20, 2)),
    "maxpool_kernel_size": hp.choice("maxpool_kernel_size", range(3, 20, 2)),
    "num_dense_layers": hp.choice("num_dense_layers", range(1, 6, 1)),
}


def hyperopt_run(inferrer: TimeSeriesInference, parameters: Dict, **kwargs) -> Dict:
    with mlflow.start_run(nested=True):
        # Log parameters
        mlflow.log_params(parameters)
        # pop the sbi related parameters, anything that is left is to do with embedding net
        batch_size = parameters.pop("batch_size")
        learning_rate = parameters.pop("learning_rate")
        hidden_features = parameters.pop("hidden_features")
        num_transforms = parameters.pop("num_transforms")
        try:
            inferrer.infer_snpe_posterior(
                embedding_net_conf=parameters,
                batch_size=batch_size,
                learning_rate=learning_rate,
                hidden_features=hidden_features,
                num_transforms=num_transforms,
            )
            mlflow.log_metric("num_epochs_to_convergence", float(inferrer.training_epochs))
            mlflow.log_metric("best_validation_log_probs", float(inferrer.best_validation_log_prob))
            # Use -ive of the log prob because hyperopt can only minimize
            return {"loss": -inferrer.best_validation_log_prob, "status": STATUS_OK}
        except RuntimeError:
            return {"loss": float("inf"), "status": STATUS_FAIL}


def load_trials(trials_space_file: Path) -> Trials:
    if os.path.exists(trials_space_file):
        with open(trials_space_file, "rb") as f:
            trials = pickle.load(f)
            print(f"\t Reusing {len(trials.trials)} trials, best was: {trials.average_best_error()}")
            return trials
    else:
        return Trials()


def tuning(inferrer: TimeSeriesInference, artifact_path: Path, max_evals: int = 5, **kwargs) -> None:
    print("\t Loading any saved hyperopt trials")
    trials = load_trials(artifact_path / "trials.pkl")

    search_space = SEARCH_SPACE

    print("\t Tuning density estimation model")
    fmin(
        fn=lambda params: hyperopt_run(inferrer=inferrer, parameters=params, **kwargs),
        space=search_space,
        trials=trials,
        algo=tpe.suggest,
        max_evals=max_evals,
    )

    print("\t Saving hyperopt trials")
    with open(artifact_path / "trials.pkl", "wb") as f:
        pickle.dump(trials, f)

    # The best results, sorted by the loss
    # The loss here is the -ive of the validation log prob
    best_trials = sorted(trials.results, key=lambda x: x["loss"], reverse=True)
    print(f"\t Best trials: \n {best_trials}")


def main() -> None:
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="CNN Tuning")
    parser.add_argument(
        "--max_evals", required=False, type=int, default=5, help="Maximum number of sampled sets of parameters "
    )
    parser.add_argument("--compute_location", required=True, type=str, choices=["local", "gcs"])
    parser.add_argument(
        "--simulator_type",
        required=True,
        type=str,
        choices=["double_rho", "herding", "double_herding", "rating_scale", "marketplace"],
    )
    args, *_ = parser.parse_known_args()

    # Choose artifact path based on compute location
    if args.compute_location == "local":
        artifact_path = LOCAL_ARTIFACT_PATH
    elif args.compute_location == "gcs":
        artifact_path = GCS_ARTIFACT_PATH
    else:
        raise ValueError(f"Unknown compute location {args.compute_location}")

    mlflow.set_experiment(f"snpe-fully-padded-cnn-timeseries-tuning")
    # Initialize the model and load context - needs to be done whether using local data or doing transforms
    print("\t Initialize inference object")
    # Parameter prior depends on the type of simulator used
    if args.simulator_type == "double_rho":
        parameter_prior = sbi_utils.BoxUniform(
            low=torch.tensor([0.0, 0.0]).type(torch.FloatTensor),
            high=torch.tensor([4.0, 4.0]).type(torch.FloatTensor),
            device="cuda",
        )
    elif args.simulator_type == "herding":
        parameter_prior = sbi_utils.BoxUniform(
            low=torch.tensor([0.0, 0.0, 0.0]).type(torch.FloatTensor),
            high=torch.tensor([4.0, 4.0, 1.0]).type(torch.FloatTensor),
            device="cuda",
        )
    elif args.simulator_type == "double_herding":
        parameter_prior = sbi_utils.BoxUniform(
            low=torch.tensor([0.0, 0.0, 0.0, 0.0]).type(torch.FloatTensor),
            high=torch.tensor([4.0, 4.0, 1.0, 1.0]).type(torch.FloatTensor),
            device="cuda",
        )
    elif args.simulator_type in ("rating_scale", "marketplace"):
        parameter_prior = sbi_utils.BoxUniform(
            low=torch.tensor([0.0, 0.0, 0.0, 0.5, 0.25, 0.25, 0.5, 0.0]).type(torch.FloatTensor),
            high=torch.tensor([4.0, 4.0, 1.0, 1.0, 0.75, 0.75, 1.0, 1.0]).type(torch.FloatTensor),
            device="cuda",
        )
    else:
        raise ValueError(f"Unknown simulator type {args.simulator_type}")
    inferrer = TimeSeriesInference(parameter_prior=parameter_prior, device="cuda")
    inferrer.load_simulator(dirname=artifact_path, simulator_type=args.simulator_type, simulation_type="timeseries")

    print("\t Tuning model")
    tuning(inferrer=inferrer, artifact_path=artifact_path, max_evals=args.max_evals)


if __name__ == "__main__":
    main()
