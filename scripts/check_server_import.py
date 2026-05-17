import torch

print("torch_version", torch.__version__, flush=True)
print("cuda_available", torch.cuda.is_available(), flush=True)

import server

print("server_import_ok", bool(server.app), flush=True)
