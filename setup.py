from setuptools import setup, find_packages


def parse_requirements(filename):
    with open(filename, 'r') as file:
        return file.read().splitlines()


setup(
    name='parseland-lib',
    version='0.0.1',
    packages=find_packages(),
    install_requires=parse_requirements('./requirements.txt'),
    url='',
    license='',
    author='nolanmccafferty',
    author_email='',
    description=''
)
