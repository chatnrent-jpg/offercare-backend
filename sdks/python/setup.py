"""VettedMe Python SDK Setup"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="vettedme",
    version="1.0.0",
    author="VettedMe Team",
    author_email="sdk@vettedme.ai",
    description="Official Python SDK for VettedMe Passport API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vettedme/vettedme-python",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "httpx>=0.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
    project_urls={
        "Documentation": "https://docs.vettedme.ai",
        "Source": "https://github.com/vettedme/vettedme-python",
        "Bug Reports": "https://github.com/vettedme/vettedme-python/issues",
    },
)
