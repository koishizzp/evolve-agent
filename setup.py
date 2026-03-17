from setuptools import setup, find_packages


setup(
    name="evolve-agent",
    version="0.1.0",
    description="Natural-language protein directed evolution agent for EvolvePro and MULTI-evolve",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "anthropic",
        "pyyaml",
        "biopython",
        "pandas",
        "numpy",
        "loguru",
    ],
    entry_points={"console_scripts": ["evolve-agent=scripts.run_agent:main"]},
)
