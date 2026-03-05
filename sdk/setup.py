from setuptools import setup, find_packages

setup(
    name="keystone",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    description="Keystone SDK — transaction governance for agent actions",
)