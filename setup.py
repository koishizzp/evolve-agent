from setuptools import find_packages, setup


setup(
    name="evolve-agent",
    version="0.2.0",
    description="Deployment-friendly protein directed evolution agent for EvolvePro and MULTI-evolve",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.115,<1",
        "uvicorn>=0.32,<1",
        "python-multipart>=0.0.9,<1",
        "openai>=1.65,<2",
        "PyYAML>=6.0,<7",
        "biopython>=1.84,<2",
        "pandas>=2.2,<3",
        "numpy>=2.0,<3",
        "loguru>=0.7,<1",
        "requests>=2.32,<3",
    ],
    entry_points={"console_scripts": ["evolve-agent=scripts.run_agent:main"]},
)
