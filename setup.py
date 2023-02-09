from setuptools import setup

setup(
    name='wahi-korero',
    version='v0.5.4',
    description='A tool for identifying and extracting segments of speech in audio.',
    url='https://github.com/TeHikuMedia/wahi-korero',
    author='@craigthelinguist, @kmahelona',
    author_email='info@tehiku.nz',
    license='Kaitiakitanga License',
    packages=['wahi_korero'],
    install_requires=[
        'pydub==0.22.1',
        'webrtcvad==2.0.10',
    ],
)
