import requests

data = {'query': 'query { allMaterials { id name category { id name } } }'}
r = requests.post('http://127.0.0.1:8000/graphql', json=data).json()

print(r)
