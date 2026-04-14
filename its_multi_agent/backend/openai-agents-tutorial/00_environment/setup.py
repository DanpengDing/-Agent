from setuptools import setup, find_packages

setup(
    name="openai-agents-tutorial",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
     "fastapi",
     "uvicorn",
     "python-dotenv",
     "openai-agents",
    ],
)
