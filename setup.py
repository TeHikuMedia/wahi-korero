from setuptools import setup

setup(
    name="wahi-korero",
    version="v0.7.6",
    description="A tool for identifying and extracting segments of speech in audio.",
    url="https://github.com/TeHikuMedia/wahi-korero",
    author="@craigthelinguist, @kmahelona",
    author_email="info@tehiku.nz",
    license="Kaitiakitanga License",
    packages=["wahi_korero"],
    install_requires=[
        "pydub==0.22.1",
        "webrtcvad==2.0.10",
    ],
    entry_points={
        "console_scripts": [
            "wahi_korero = wahi_korero.cli:main",
        ]
    },
)
