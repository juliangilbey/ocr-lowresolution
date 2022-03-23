# ocr-lowresolution

Source code for low resolution OCR experiments

The source for the low-resolution version of Tesseract can be found at
[https://github.com/juliangilbey/tesseract/tree/lores-v1.0](https://github.com/juliangilbey/tesseract/tree/lores-v1.0)

More information can be found in our preprint here:
[https://arxiv.org/abs/2105.04515](https://arxiv.org/abs/2105.04515)


## Overview of the code

There are two separate tasks that the code in this repository
performs:

* Creating Tesseract `traineddata` files for low resolution images
* Running Tesseract on low resolution images to perform OCR

We describe each of these in turn; you first need to build and install
the modified version of tesseract pointed to above to use the code
here.

There is also a file called `scripts.sh` which contains a variety of
(briefly commented) shell commands that can be adapted to run the code
to perform the training and OCR.

### Creating Tesseract traineddata files

As described in the preprint, pre-trained `traineddata` files are
available on Zenodo, so this is only required if you are reproducing
the experiments.

Creating `traineddata` files is achieved using `make`.  You will need
to modify the start of the `Makefile` for your local setup.  In
particular:

* Modify the `TESSTRAIN` line at the start of the `Makefile` to point
    to a directory in which you will store all of your training data.
    
* You may wish to modify the `TESSDATA` if you wish to store the
    training data elsewhere; by default it is `$(TESSTRAIN)/tessdata`.

* You will have to change the `TESSCONFIGS` line to point to the
    location of tesseract config files.  The version in GitHub works
    for macOS with MacPorts, while for a Linux distribution,
    `/usr/share/tesseract-ocr/4.00/tessdata/configs` may be more
    appropriate (assuming that the locally built modified Tesseract is
    installed overwriting the standard version).

* If your low-resolution `tesseract` executable is not in your `PATH`
    (before any non-modified `tesseract`), you will need to set
    `TESSBINDIR` to the directory containing the low-resolution
    `tesseract`.

* Depending on the system you are using, the available fonts may be
    different.  Modify the `FONTS` setting if so.  These fonts must
    work with LuaLaTeX.

Before running `make` for the first time, you will need training text
data split into manageable chunks.  To replicate the experiments,
download Tesseract's own training data from
https://github.com/tesseract-ocr/langdata_lstm/raw/main/eng/eng.training_text
and save it in the directory `$(TESSDATA)/eng`.  Then in the
directory `$(TESSDATA)/eng`, run the command: `split -a 3 -l 160
eng.training_text eng.training_text_split_`

(If you want to use different training texts, replace
`eng.training_text` in this command with a different file of training
text.)

The training has been split into three steps, which must be run in
order:

* `make training-images`: this makes low-resolution images from the
    training text
* `make lists`: this creates some intermediate files necessary for the
    training step
* `make training`: this performs the actual training

By default, the resolution is 60 dpi, the scaling method is bicubic
and there is no Gaussian blur.  (See the preprint for more details on
these.)  These can be changed by setting Makefile parameters on the
command line as follows:

    make RES=75 SCALING=0 BLUR=1 training-images

(and the same parameters should be used for `make lists` and `make
training`).  The `RES` parameter specifies the resolution, `SCALING`
is 0 for box, 1 for bilinear and 2 for bicubic, and `BLUR` specifies
the Gaussian blur in pixels.

The directory which will contain the resulting `traineddata` file is
`$(TESSTRAIN)/data$(RES)_$(SCALING_NAME)+$(BLUR)`

It is also possible to run the training in steps using the
`trainingstep` target; see the Makefile for more details.  There are
also some clean targets; again, see the Makefile.


### Performing OCR on low-resolution images

This is achieved using the script `ocr_images.py`.  Running
`ocr_images.py --help` describes all of the commandline options.  Here
is an example of how it can be used:

    ocr_images.py -r 60 -s C0,L0,B0,B0.5,B1,B1.5,B2 -g image.gt.txt \
        --outbase image --tessdata-path /path/to/tessdata/ -w image.png

This processes the 60 dpi image `image.png`, whose known ground truth
text is `image.gt.txt`.  The low-resolution `traineddata` files are in
the directory `/path/to/tessdata`; this should match the value of
`TESSDATA` used in the Makefile in the first stage.  The output files
will have the prefix `image`, and `-w` specifies that word-level
metrics will be generated, specifying how accurate the OCR performance
was.  Finally, this command will process the image multiple times and
merge the results: it will use the `C0` network (bicubic with no
further Gaussian blurring), then `L0` (bilinear with no further
Gaussian blurring), then `B0`, `B0.5`, ..., `B2` (box with Gaussian
blurring of 0, 0.5, ..., 2 pixels standard deviation).  This requires
the presence of `traineddata` files for each of these scalings.
