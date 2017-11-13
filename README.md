# stressoctaviaapi

This is a quick and (very) dirty app I wrote to stress certain aspects of
the OpenStack Octavia API.  It's intent is to exercise the database locking
used in the Octavia API.
This code is lightly tested in my devstack development environment.
It may/may not work and/or be complete enough for yours.
This type of testing will be integrated into the Octavia tempest plugin at
some point.
