"""Deploy Omi GPU services (VAD + speaker-identification) to Modal.

Follows the upstream architecture: `backend/modal/main.py` served as a GPU web
service (upstream runs the same code from their private gcr registry inside
GKE/Modal). One documented deviation for this fork: public python:3.11-slim
base instead of the private `gcr.io/based-hardware-dev` image.

Deploy:
    modal token set --token-id wk-... --token-secret ws-...
    modal secret create omi-gpu-secrets HUGGINGFACE_TOKEN=hf_xxx SERVICE_ACCOUNT_JSON='{"type":...}'
    modal deploy selfhost/modal/deploy_omi_gpu.py

Backend wiring (VPS .env):
    HOSTED_VAD_API_URL=https://<workspace>--omi-gpu-services-gpuserviceserve.modal.run/v1/vad  # noqa: E501
    HOSTED_SPEECH_PROFILE_API_URL=https://<workspace>--omi-gpu-services-gpuserviceserve.modal.run  # noqa: E501
"""

import modal

app = modal.App("omi-gpu-services")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git", "gcc", "g++", "curl")
    .pip_install_from_requirements("requirements-gpu.txt")
    .add_local_dir("src", remote_path="/app", copy=True)
    .workdir("/app")
)


@app.function(
    image=image,
    gpu="T4",
    timeout=600,
    scaledown_window=300,
    secrets=[modal.Secret.from_name("omi-gpu-secrets")],
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def gpu_services():
    from main import app as fastapi_app

    return fastapi_app
