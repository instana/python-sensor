To regenerate from the proto file:

```bash
pip install grpcio grpcio-tools
python -m grpc_tools.protoc --proto_path=. ./stanaas.proto --python_out=. --grpc_python_out=.
```

Inspired from: https://technokeeda.com/programming/grpc-python-tutorial/