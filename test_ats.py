import requests
import json

url = "http://localhost:8000/analyze_resume"
data = {
    "resume_text": "Jane Doe. Cloud Architect with 10 years experience in AWS and Kubernetes. Led migrations for Fortune 500 companies.",
    "target_role": "Junior Frontend Developer"
}

print(f"Testing analysis for role: {data['target_role']}")
response = requests.post(url, json=data)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(json.dumps(response.json(), indent=2))
else:
    print(response.text)

data2 = {
    "resume_text": "Fresh Graduate. Only knows HTML and basic CSS. No industry experience.",
    "target_role": "Senior Cloud Architect"
}
print(f"\nTesting analysis for role: {data2['target_role']}")
response2 = requests.post(url, json=data2)
print(f"Status: {response2.status_code}")
if response2.status_code == 200:
    print(json.dumps(response2.json(), indent=2))
else:
    print(response2.text)
