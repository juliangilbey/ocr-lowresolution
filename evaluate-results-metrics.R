library(tidyverse)
library(stringi)

# Produce all-merged.csv using merge-csvs.py
allcsv <- "/Volumes/JULIAN\ GILBEY\ 2/Cognizant/processed-data/all-merged-res60-001.csv"
dotext <- TRUE

mmetric_all <- read_csv(allcsv,
                        col_types = cols(text = col_character(),
                                         font = col_character(),
                                         page = col_integer(),
                                         blurring = col_character(),
                                         chars = col_integer(),
                                         words = col_integer(),
                                         cdist = col_integer(),
                                         wdist = col_integer(),
                                         cdistq = col_integer(),
                                         wdistq = col_integer()))

summarise_mmetric_by <- function(m, doby1, doby2) {
  doby1 <- enquo(doby1)
  doby2 <- enquo(doby2)
  m %>%
    group_by(!!doby1, !!doby2) %>%
    summarise(totchar = sum(chars),
              totwords = sum(words),
              totcdist = sum(cdist),
              totwdist = sum(wdist),
              totcdistq = sum(cdistq),
              totwdistq = sum(wdistq)) %>%
    mutate(CLA = 100 * (1 - totcdist / totchar),
           WLA = 100 * (1 - totwdist / totwords),
           CLAq = 100 * (1 - totcdistq / totchar),
           WLAq = 100 * (1 - totwdistq / totwords))
}

graph_mmetric_by <- function(msum, doby1, doby2, doby3) {
  doby1 <- enquo(doby1)
  doby2 <- enquo(doby2)
  doby3 <- enquo(doby3)

  ggplot(data = msum,
         mapping = aes(x = !!doby1, y = !!doby3)) +
    geom_point(aes(color = !!doby2)) +
    theme(axis.text.x = element_text(angle = 90))
}

mmetric_font_blur <- summarise_mmetric_by(mmetric_all, font, blurring)
if (dotext) {
  mmetric_text_blur <- summarise_mmetric_by(mmetric_all, text, blurring)
  mmetric_text_font <- summarise_mmetric_by(mmetric_all, text, font)
}

if (dotext) {
  graph_mmetric_by(mmetric_text_blur, text, blurring, CLA)
  graph_mmetric_by(mmetric_text_blur, blurring, text, CLA)
}
graph_mmetric_by(mmetric_font_blur, font, blurring, CLA)
graph_mmetric_by(mmetric_font_blur, blurring, font, CLA)
if (dotext) {
  graph_mmetric_by(mmetric_text_font, text, font, CLA)
  graph_mmetric_by(mmetric_text_font, font, text, CLA)
}

if (dotext) {
  graph_mmetric_by(mmetric_text_blur, text, blurring, WLA)
  graph_mmetric_by(mmetric_text_blur, blurring, text, WLA)
}
graph_mmetric_by(mmetric_font_blur, font, blurring, WLA)
graph_mmetric_by(mmetric_font_blur, blurring, font, WLA)
if (dotext) {
  graph_mmetric_by(mmetric_text_font, text, font, WLA)
  graph_mmetric_by(mmetric_text_font, font, text, WLA)
}

if (dotext) {
  graph_mmetric_by(mmetric_text_blur, text, blurring, CLAq)
  graph_mmetric_by(mmetric_text_blur, blurring, text, CLAq)
}
graph_mmetric_by(mmetric_font_blur, font, blurring, CLAq)
graph_mmetric_by(mmetric_font_blur, blurring, font, CLAq)
if (dotext) {
  graph_mmetric_by(mmetric_text_font, text, font, CLAq)
  graph_mmetric_by(mmetric_text_font, font, text, CLAq)
}

if (dotext) {
  graph_mmetric_by(mmetric_text_blur, text, blurring, WLAq)
  graph_mmetric_by(mmetric_text_blur, blurring, text, WLAq)
}
graph_mmetric_by(mmetric_font_blur, font, blurring, WLAq)
graph_mmetric_by(mmetric_font_blur, blurring, font, WLAq)
if (dotext) {
  graph_mmetric_by(mmetric_text_font, text, font, WLAq)
  graph_mmetric_by(mmetric_text_font, font, text, WLAq)
}
