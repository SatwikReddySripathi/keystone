from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="keystone-governance",          # unique PyPI name
    version="0.1.0",
    author="Sripathi SA",
    author_email="sripathi.sa@northeastern.edu",
    description="Drop-in transaction governance for AI agent workflows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YOUR_GITHUB_USERNAME/keystone",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=["requests>=2.28.0"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
        "Topic :: Security",
        "Intended Audience :: Developers",
    ],
    keywords="ai agents governance policy approval audit",
)
