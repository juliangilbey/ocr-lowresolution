#!/bin/bash

echo "Don't run this script; these are just shell script lines which"
echo "might be useful to you independently of each other!"
exit 0

# used for building the training line data in parallel
res=60; for i in $(cd ~/Cognizant/tesstrain/tessdata/eng && ls *_split* | cut -c 25- | perl -lne '($. - 7) % 8 or print'); do nice -n 19 make RES=$res /Users/jdg/Cognizant/tesstrain/linedata/linedata$res/$i-done; done
# then
res=60; make RES=$res ground-images

# used for making the training-images
scaling=2; blur=0; res=60; make RES=$res SCALING=$scaling BLUR=$blur training-images

# used for building the lstmf files in batches (so a single error does not
# crash the whole build)
scaling=2; sname=bicubic; blur=0; res=60; for i in $(cd ~/Cognizant/tesstrain/tessdata/eng && ls *_split* | cut -c 25-); do nice -n 19 make RES=$res SCALING=$scaling BLUR=$blur /Users/jdg/Cognizant/tesstrain/linedata/linedata${res}_$sname+$blur/$i-lstmfdone; done
# then
scaling=2; blur=0; res=60; make RES=$res SCALING=$scaling BLUR=$blur lists

# doing the whole training in one go
scaling=2; blur=0; res=60; make RES=$res SCALING=$scaling BLUR=$blur lists && make RES=$res SCALING=$scaling BLUR=$blur training

# doing the training in 10 parts with nohup
scaling=2; blur=0; res=60; nohup nice -n 19 ./maketrainingsteps $scaling $blur $res &> training$res-${scaling}_$blur.out &

# processing all the pages
for d in *; do cd $d; for f in *-simulated-60dpi.png; do fbase=${f%-simulated-60dpi.png}; echo $fbase; for sds in C0 L0 B0 B0.5 B1 B1.5 B2 C0,L0,B0,B0.5,B1,B1.5,B2; do ../../ocr-experimentation/ocr_images.py -s $sds -g $fbase.gt.txt --outbase $fbase --tessdata-path /alt/applic/user-maint/jdg18/share/tesseract-ocr/tessdata/ -w $f; done; done; cd ..; done
