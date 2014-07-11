from setuptools import setup, find_packages
import jade_tools

setup(
    name='django-jade-tools',
    version=jade_tools.__version__,
    packages=find_packages(exclude=['testproject']),
    url='http://github.com/celerityweb/django-jade-tools',
    license=jade_tools.__license__,
    author='Joshua "jag" Ginsberg',
    author_email='jginsberg@celerity.com',
    description='Tools to help backend developers working in Django and '
                'frontend developers working in Jade coordinate their efforts '
                'better.'
)
