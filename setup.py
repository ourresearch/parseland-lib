from setuptools import setup


def parse_requirements(filename):
    with open(filename, 'r') as file:
        return file.read().splitlines()


setup(
    name='parseland-lib',
    version='0.0.1',
    install_requires=parse_requirements('./requirements.txt'),
    url='',
    license='',
    author='nolanmccafferty',
    author_email='',
    description=''
)
