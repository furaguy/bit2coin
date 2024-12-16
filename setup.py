# setup.py
from setuptools import setup, find_packages

setup(
    name="bit2coin",
    version="0.1.0",  # Match version in pyproject.toml
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "cryptography>=3.4",
        "fastapi>=0.68.1",
        "uvicorn>=0.15.0",
        "web3>=5.24.0",
        "eth-account>=0.5.6",
        "cryptography>=3.4.8",
        "pydantic>=1.8.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.1",
            "pytest-mock>=3.10",
            "black>=23.0",
            "isort>=5.12",
            "flake8>=6.0",
            "mypy>=1.0"
        ],
    },
    author="Your Name",
    author_email="your.email@example.com",
    description="A blockchain implementation in Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/bit2coin",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)