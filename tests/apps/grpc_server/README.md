To regenerate from the proto file:

```bash
pip install grpcio grpcio-tools protobuf
python -m grpc_tools.protoc --proto_path=. --python_out=. --grpc_python_out=. ./stan.proto
```

Inspired by: https://technokeeda.com/programming/grpc-python-tutorial/