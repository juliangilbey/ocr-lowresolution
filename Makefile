# makefile loosely based on one from ocrd-train,
# now https://github.com/tesseract-ocr/tesstrain

# Make sure that sort always uses the same sort order.
export LC_ALL := C

SHELL := /bin/bash
# Training directory where all the data lives
TESSTRAIN = $(HOME)/Cognizant/tesstrain
# The data directory we work within
TESSDATA =  $(TESSTRAIN)/tessdata
# Location of tesseract distribution config files
TESSCONFIGS = /opt/local/share/tessdata/configs
# these are for when we're running testing code
# eg: TESSENV = DYLD_LIBRARY_PATH=/Users/jdg/Cognizant/tesseract/src/api/.libs
TESSENV = 
# if non-empty, this must end in a slash
# eg: TESSBINDIR = /Users/jdg/Cognizant/tesseract/src/api/.libs/
# eg: TRAININGBINDIR = /Users/jdg/Cognizant/tesseract/src/training/.libs/
TESSBINDIR = 
TRAININGBINDIR = 

# Resolution we're working with
RES = 60

# Scaling method (0=box, 1=bilinear, 2=bicubic)
SCALING = 2
SCALING_NAME = $(shell if [ $(SCALING) = "0" ]; then echo "box"; elif [ $(SCALING) = "1" ]; then echo "bilinear"; else echo "bicubic"; fi)

# Additional Gaussian blur (sd in pixels)
BLUR = 0

# Name of language being trained. Default: $(LANG_NAME)
LANG_NAME = eng

# Name of the model to continue from. Default: $(START_MODEL)
START_MODEL = 

# Data directory (will contained traineddata file)
DATA = $(TESSTRAIN)/data$(RES)_$(SCALING_NAME)+$(BLUR)

# Where the training text line images and ground truths live
GROUND_IMAGES_DIR = $(TESSTRAIN)/linedata/linedata$(RES)
TRAINING_TEXT_DIR = $(GROUND_IMAGES_DIR)_$(SCALING_NAME)+$(BLUR)

# Max iterations. Default: $(MAX_ITERATIONS)
MAX_ITERATIONS = 80000

# Page segmentation mode. Default: $(PSM)
PSM = 6

# Resolution
DPI = 300

# Ratio of train / eval training data. Default: $(RATIO_TRAIN)
RATIO_TRAIN = 0.90

# Where the last checkpoint is saved
LAST_CHECKPOINT = $(DATA)/checkpoints/$(LANG_NAME)_checkpoint
# When doing the checkpoint in stages
STEP = 1
STEP1 := $(shell echo $(STEP) - 1 | bc)
STEP0 := $(shell printf "%03d" $(STEP))
STEP01 := $(shell printf "%03d" $(STEP1))
LAST_CHECKPOINT_N = $(DATA)/checkpoints/$(LANG_NAME)$(STEP0)_checkpoint
TOTSTEPS = 10

# Fonts to be trained on
FONTS = Arial,Avenir,Baskerville,Calibri,Chalkboard,Comic_Sans_MS,Courier_New,FrankRuehlCLM-Medium,Franklin_Gothic_Book,Futura,Gill_Sans_MT,Helvetica,Lucida_Console,Lucida_Sans_Unicode,Menlo,Palatino,Tahoma,Trebuchet_MS,Times_New_Roman,Verdana

# Font sizes to be trained on
SIZES = 9,10,11,12

# Whether to use rotations in training
ROTATIONS = cycle

help:
	@echo "Please see the Makefile for details of the targets"
	@echo "and variables"


## Making training data

# We break up the training text images into lots of subdirectories to keep
# the directory sizes manageable
# The training texts are created using:
# split -a 3 -l 160 [...]/langdata_lstm/eng/eng.training_text eng.training_text_split_
# The choice of 160 lines is because we are using 20 fonts * 4 sizes * 2 rotations
# This also means that we can run make separately on different directories,
# so a long series of shell-controlled make jobs can successfully process
# most of them without giving up completely at the first error.

TRAINING_TEXTS := $(sort $(patsubst $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).training_text_split_%,%,$(wildcard $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).training_text_split_*)))

GROUND_IMAGES_DONES := $(patsubst %,$(GROUND_IMAGES_DIR)/%-done,$(TRAINING_TEXTS))
GROUND_IMAGES_ALL_DONE := $(GROUND_IMAGES_DIR)/images-done

TRAINING_TEXTS_IMAGES_ALL_DONE := $(TRAINING_TEXT_DIR)/images-done

ground-images: $(GROUND_IMAGES_ALL_DONE)

$(GROUND_IMAGES_ALL_DONE): $(GROUND_IMAGES_DIR) $(GROUND_IMAGES_DONES)
	touch $@

$(GROUND_IMAGES_DIR)/%-done: $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).training_text_split_%
	mkdir -p $(GROUND_IMAGES_DIR)/$*
	./gen_tess_training_data.py --resolution $(RES) \
	   --outdir $(GROUND_IMAGES_DIR)/$* --outbase $* \
	   --fonts $(FONTS) --fontsizes $(SIZES) --rotations $(ROTATIONS) \
	   $<
	touch $@

$(GROUND_IMAGES_DIR):
	mkdir -p $(GROUND_IMAGES_DIR)

training-images: $(GROUND_IMAGES_ALL_DONE) $(TRAINING_TEXTS_IMAGES_ALL_DONE)

$(TRAINING_TEXTS_IMAGES_ALL_DONE): $(GROUND_IMAGES_ALL_DONE) $(TRAINING_TEXT_DIR)
	touch $@

$(TRAINING_TEXT_DIR): $(GROUND_IMAGES_ALL_DONE)
	cp -a $(GROUND_IMAGES_DIR) $(TRAINING_TEXT_DIR)

# Create lists of lstmf filenames for training and eval
ifeq ($(wildcard $(TRAINING_TEXTS_IMAGES_ALL_DONE)),)
lists:
	@echo "You have to run 'make training-images' before you can run 'make lists'"
training:
	@echo "You have to run 'make training-images' and 'make lists' before you can run 'make training'"
else

# We break up the lstmf creation into subsections for the same reason
# as above
LSTMF_DONES := $(patsubst %,$(TRAINING_TEXT_DIR)/%-lstmfdone,$(TRAINING_TEXTS))

ALL_LSTMF = $(DATA)/all-lstmf

lists: $(ALL_LSTMF) $(DATA)/list.train $(DATA)/list.eval

$(DATA):
	mkdir -p $(DATA)/eng/configs
	cp $(TESSCONFIGS)/hocr $(TESSCONFIGS)/txt $(DATA)/eng/configs

$(DATA)/list.train: $(DATA) $(ALL_LSTMF)
	total=`cat $(ALL_LSTMF) | wc -l`; \
	   no=`echo "$$total * $(RATIO_TRAIN) / 1" | bc`; \
	   head -n "$$no" $(ALL_LSTMF) > "$@"

$(DATA)/list.eval: $(DATA) $(ALL_LSTMF)
	total=`cat $(ALL_LSTMF) | wc -l` \
	   no=`echo "$$total - ($$total * $(RATIO_TRAIN)) / 1" | bc`; \
	   tail -n "$$no" $(ALL_LSTMF) > "$@"

$(TRAINING_TEXT_DIR)/%-lstmfdone: $(TRAINING_TEXT_DIR)/%-done
	for b in $(TRAINING_TEXT_DIR)/$*/*.png; do \
	    $(MAKE) $${b%.png}.lstmf; \
	done
	touch $@

$(ALL_LSTMF): $(DATA)/seed.txt $(LSTMF_DONES)
	find $(TRAINING_TEXT_DIR) -name '*.lstmf' | sort | sort -R --random-source=$(DATA)/seed.txt > "$@"

$(DATA)/seed.txt: $(DATA)
	echo 'This is a seed text file; do not modify' > $@

%.lstmf: %-lstm.box %.box
	$(TESSENV) $(TESSBINDIR)tesseract --dpi 300 -l eng -c low_resolution_input=true -c low_resolution_dpi=$(RES) -c low_resolution_scaling=$(SCALING) -c low_resolution_blurring=$(BLUR) --psm $(PSM) $*.png $* lstm.train

%-lstm.box: %.png %.box
	$(TESSENV) $(TESSBINDIR)tesseract --dpi 300 -l eng -c low_resolution_input=true -c low_resolution_dpi=$(RES) -c low_resolution_scaling=$(SCALING) -c low_resolution_blurring=$(BLUR) --psm $(PSM) $*.png $*-lstm lstmbox
	./fix_lstm_box.py $*

## Training

ifeq ($(wildcard $(ALL_LSTMF)),)
training:
	@echo "You have to run 'make lists' before you can run 'make training'"
else

$(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).traineddata:
	cd $(TESSDATA) && wget "https://github.com/tesseract-ocr/tessdata_best/raw/master/$(notdir $@)"

$(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).lstm: $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).traineddata
	cd $(TESSDATA)/$(LANG_NAME) && \
	  $(TESSENV) $(TRAININGBINDIR)combine_tessdata -e $(LANG_NAME).traineddata $(LANG_NAME).lstm

$(DATA)/$(LANG_NAME).traineddata: $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).traineddata
	ln -s $< $@

$(DATA)/$(LANG_NAME).lstm: $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).lstm
	ln -s $< $@

training: $(DATA)/$(LANG_NAME)/$(LANG_NAME).traineddata

$(LAST_CHECKPOINT): $(DATA)/$(LANG_NAME).lstm $(DATA)/$(LANG_NAME).traineddata
	mkdir -p $(DATA)/checkpoints
	$(TESSENV) $(TRAININGBINDIR)lstmtraining \
	  --model_output $(DATA)/checkpoints/$(LANG_NAME) \
	  --continue_from $(DATA)/$(LANG_NAME).lstm \
	  --traineddata $(DATA)/$(LANG_NAME).traineddata \
	  --max_iterations $(MAX_ITERATIONS) --target_error_rate 0.01 \
	  --train_listfile $(DATA)/list.train \
	  --eval_listfile $(DATA)/list.eval $(LSTMEXTRA)

$(DATA)/$(LANG_NAME)/$(LANG_NAME).traineddata: $(LAST_CHECKPOINT)
	$(TESSENV) $(TRAININGBINDIR)lstmtraining \
	  --stop_training \
	  --continue_from $(LAST_CHECKPOINT) \
	  --traineddata $(DATA)/$(LANG_NAME).traineddata \
	  --model_output $@ $(LSTMEXTRA)

# A step-by-step version of the above
# This splits the training into $(TOTSTEPS) steps

$(DATA)/list1.train: $(DATA)/list.train
	cd $(DATA) && \
	  split --numeric-suffixes=1 --number=l/$(TOTSTEPS) --suffix-length=3 \
	    --additional-suffix=.train list.train list

$(DATA)/list1.eval: $(DATA)/list.eval
	cd $(DATA) && \
	  split --numeric-suffixes=1 --number=l/$(TOTSTEPS) --suffix-length=3 \
	    --additional-suffix=.eval list.eval list

$(DATA)/$(LANG_NAME)$(STEP0).traineddata: $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).traineddata
	@echo "Linking $(DATA)/$(LANG_NAME)$(STEP0).traineddata"
	@if [ 1 -gt "$(STEP)" ]; then \
	    echo "STEP must be at least 1" >&2; \
	    exit 1; \
	elif [ $(TOTSTEPS) -lt "$(STEP)" ]; then \
	    echo "STEP must be at most $(TOTSTEPS)" >&2; \
	    exit 1; \
	fi
	@if [ $(STEP) -eq 1 ]; then \
	    ln -s $< $@; \
	elif [ -f $(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP01).traineddata ]; then \
	    ln -s $(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP01).traineddata $@; \
	else \
	    echo "$(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP01).traineddata does not exist" >&2; \
	    echo "Run make training with STEP = $(STEP1) first" >&2; \
	    exit 1; \
	fi

$(DATA)/$(LANG_NAME)$(STEP0).lstm: $(TESSDATA)/$(LANG_NAME)/$(LANG_NAME).lstm
	@echo "Extracting $(DATA)/$(LANG_NAME)$(STEP0).lstm"
	@if [ 1 -gt "$(STEP)" ]; then \
	    echo "STEP must be at least 1" >&2; \
	    exit 1; \
	elif [ $(TOTSTEPS) -lt "$(STEP)" ]; then \
	    echo "STEP must be at most $(TOTSTEPS)" >&2; \
	    exit 1; \
	fi
	@if [ $(STEP) -eq 1 ]; then \
	    ln -s $< $@; \
	elif [ -f $(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP01).traineddata ]; then \
	    cd $(DATA)/$(LANG_NAME) && \
	      $(TESSENV) $(TRAININGBINDIR)combine_tessdata -e $(LANG_NAME)$(STEP01).traineddata $(LANG_NAME).lstm || exit 1; \
	    mv $(DATA)/$(LANG_NAME)/$(LANG_NAME).lstm $@; \
	else \
	    echo "$(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP01).traineddata does not exist" >&2; \
	    echo "Run make training with STEP = $(STEP1) first" >&2; \
	    exit 1; \
	fi

trainingstep: $(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP0).traineddata

$(LAST_CHECKPOINT_N): $(DATA)/$(LANG_NAME)$(STEP0).lstm $(DATA)/$(LANG_NAME)$(STEP0).traineddata $(DATA)/list1.train $(DATA)/list1.eval
	mkdir -p $(DATA)/checkpoints
	$(TESSENV) $(TRAININGBINDIR)lstmtraining \
	  --model_output $(DATA)/checkpoints/$(LANG_NAME)$(STEP0) \
	  --continue_from $(DATA)/$(LANG_NAME)$(STEP0).lstm \
	  --traineddata $(DATA)/$(LANG_NAME)$(STEP0).traineddata \
	  --max_iterations $(MAX_ITERATIONS) --target_error_rate 0.01 \
	  --train_listfile $(DATA)/list$(STEP0).train \
	  --eval_listfile $(DATA)/list$(STEP0).eval $(LSTMEXTRA)

$(DATA)/$(LANG_NAME)/$(LANG_NAME)$(STEP0).traineddata: $(LAST_CHECKPOINT_N)
	$(TESSENV) $(TRAININGBINDIR)lstmtraining \
	  --stop_training \
	  --continue_from $(LAST_CHECKPOINT_N) \
	  --traineddata $(DATA)/$(LANG_NAME)$(STEP0).traineddata \
	  --model_output $@ $(LSTMEXTRA)

# Don't delete the last checkpoint if lstmtraining dies for some reason
.PRECIOUS: $(LAST_CHECKPOINT) $(LAST_CHECKPOINT_N)

endif # ifeq ($(wildcard $(ALL_LSTMF)),)
endif # ifeq ($(wildcard $(TRAINING_TEXTS_IMAGES_ALL_DONE)),)


## Cleaning
clean:
	rm -rf $(DATA)/$(LANG).lstm $(DATA)/$(LANG).traineddata \
	   $(DATA)/checkpoints
	if [ -d $(TRAINING_TEXT_DIR) ]; then find $(TRAINING_TEXT_DIR) -name '*-lstm.box' -delete; fi

clean-images:
	rm -rf $(TRAINING_TEXT_DIR)
	rm -rf $(DATA)/$(LANG).lstm $(DATA)/$(LANG).traineddata \
	   $(DATA)/$(LANG)$(STEP0).lstm $(DATA)/$(LANG)$(STEP0).traineddata \
	   $(DATA)/checkpoints $(DATA)/all-lstmf $(DATA)/list*.train \
	   $(DATA)/list*.eval $(DATA)/seed.txt
	@echo "You may have to clean $(DATA)/$(LANG)*.lstm and $(DATA)/$(LANG)*.traineddata manually"

veryclean:
	rm -rf $(TRAINING_TEXT_DIR)
	rm -rf $(GROUND_IMAGES_DIR)
	rm -rf $(DATA)

.PHONY: ground-images training-images lists training trainingstep \
	clean clean-images veryclean
