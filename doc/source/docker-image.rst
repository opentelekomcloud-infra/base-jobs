Container Images
================

The jobs described in this section all work together to handle the
full gating process for continuously deployed container images.  They
can be used to build or test images which rely on other images using
the full power of Zuul's speculative execution.

There are a few key concepts to keep in mind:

A *buildset* is a group of jobs all running on the same change.

A *buildset registry* is a container image registry which is used to
store speculatively built images for the use of jobs in a single
buildset.  It holds the differences between the current state of the
world and the future state if the change in question (and all of its
dependent changes) were to merge.  It must be started by one of the
jobs in a buildset, and it ceases to exist once that job is complete.

An *intermediate registry* is a long-running registry that is used to
store images created for unmerged changes for use by other unmerged
changes.  It is not publicly accessible and is intended only to be
used by Zuul in order to transfer artifacts from one buildset to
another.  OpenDev maintains such a registry.

With these concepts in mind, the jobs described below implement the
following workflow for a single change:

.. _buildset_image_transfer:

.. seqdiag::
   :caption: Buildset registry image transfer

   seqdiag image_transfer {
     Ireg [label="Intermediate\nRegistry"];
     Breg [label="Buildset\nRegistry"];
     Bjob [label="Image Build Job"];
     Djob [label="Deployment Test Job"];

     Ireg -> Breg [label='Images from previous changes'];
     Breg -> Bjob [label='Images from previous changes'];
     Breg <- Bjob [label='Current image'];
     Ireg <- Breg [noactivate, label='Current image'];
     Breg -> Djob [label='Current and previous images'];
     Breg <- Djob [style=none];
     Ireg <- Breg [style=none];
   }

The intermediate registry is always running and the buildset registry
is started by a job running on a change.  The "Image Build" and
"Deployment Test" jobs are example jobs which might be running on a
change.  Essentially, these are image producer or consumer jobs
respectively.

There are two ways to use the jobs described below:

A Repository with Producers and Consumers
-----------------------------------------

The first is in a repository where images are both produced and
consumed.  In this case, we can expect that there will be at least one
image build job, and at least one job which uses that image (for
example, by performing a test deployment of the image).  In this case
we need to construct a job graph with dependencies as follows:

.. blockdiag::

   blockdiag dependencies {
     obr [label='opendev-\nbuildset-registry'];
     bi [label='build-image'];
     ti [label='test-image'];

     obr <- bi <- ti;
   }

The :zuul:job:`opendev-buildset-registry` job will run first and
automatically start a buildset registry populated with images built
from any changes which appear ahead of the current change.  It will
then return its connection information to Zuul and pause and continue
running until the completion of the build and test jobs.

The build-image job should inherit from
:zuul:job:`opendev-build-docker-image`, which will ensure that it is
automatically configured to use the buildset registry.

The test-image job is something that you will create yourself.  There
is no standard way to test or deploy an image, that depends on your
application.  However, there is one thing you will need to do in your
job to take advantage of the buildset registry.  In a pre-run playbook,
use the `use-buildset-registry
<https://zuul-ci.org/docs/zuul-jobs/roles.html#role-use-buildset-registry>`_
role:

.. code:: yaml

   - hosts: all
     roles:
       - use-buildset-registry

That will configure the docker daemon on the host to use the buildset
registry so that it will use the newly built version of any required
images.

A Repository with Only Producers
--------------------------------

The second way to use these jobs is in a repository where an image is
merely built, but not deployed.  In this case, there are no consumers
of the buildset registry other than the image build job, and so the
registry can be run on the job itself.  In this case, you may omit the
:zuul:job:`opendev-buildset-registry` job and run only the
:zuul:job:`opendev-build-docker-image` job.

Publishing an Image
-------------------

So far we've covered the image building process.  This system also
provides two more jobs that are used in publishing images to Docker
Hub.

The :zuul:job:`opendev-upload-docker-image` job does everything the
:zuul:job:`opendev-build-docker-image` job does, but it also uploads
the built image to Docker Hub using an automatically-generated and
temporary tag.  The "build" job is designed to be used in the
*check* pipeline, while the "upload" job is designed to take its
place in the *gate* pipeline.  By front-loading the upload to Docker
Hub, we reduce the chance that a credential or network error will
prevent us from publishing an image after a change lands.

The :zuul:job:`opendev-promote-docker-image` jobs is designed to be
used in the *promote* pipeline and simply re-tags the image on Docker
Hub after the change lands.

Keeping in mind that everything described above in
:ref:`buildset_image_transfer` applies to the
:zuul:job:`opendev-upload-docker-image` job, the following illustrates
the additional tasks performed by the "upload" and "promote" jobs:

.. seqdiag::

   seqdiag image_transfer {
     DH [activated, label="Docker Hub"];
     Ujob [label="upload-image"];
     Pjob [label="promote-image"];

     DH -> Ujob [style=none];
     DH <- Ujob [label='Current image with temporary tag'];
     DH -> Pjob [label='Current image manifest with temporary tag',
                 note='Only the manifest
                       is transferred,
                       not the actual
                       image layers.'];
     DH <- Pjob [label='Current image manifest with final tag'];
   }

Jobs
----

.. zuul:autojob:: opendev-buildset-registry

.. zuul:autojob:: opendev-buildset-registry-consumer

.. zuul:autojob:: opendev-build-docker-image-base

.. zuul:autojob:: opendev-build-docker-image

.. zuul:autojob:: opendev-intermediate-registry

.. zuul:autojob:: opendev-upload-docker-image

.. zuul:autojob:: opendev-promote-docker-image
