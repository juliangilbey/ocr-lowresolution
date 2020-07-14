library(tidyverse)
library(stringi)
library(ggthemes)

imgdir <- "/Volumes/JULIAN GILBEY 2/Cognizant/processed-data/linedata75-001"
csv_in <- file.path(imgdir, "wmetric-all.csv")
csv_out <- ""  #file.path(imgdir, "wmetric-all.csv")
suffix <- ""
linedata <- TRUE
setwd(imgdir)

read_wmetrics <- function(f) {
  if (linedata) {
    fparts <- stri_match_first_regex(f,
                    str_c("(?:.*/|^)([a-z-]*)_([A-Z][A-Za-z_-]*)_",
                          "(\\d+)-([-\\w]*)-wmetrics\\.csv"))
  } else {
    fparts <- stri_match_first_regex(f,
                    str_c("(?:.*/|^)([a-z-]*)-([A-Z][A-Za-z-]*)-",
                          "page(\\d)-([-\\w]*)-wmetrics\\.csv"))
  }
  fdata <- read_csv(f, skip = 1,
                    col_names = c("word", "conf", "correct"),
                    col_types = cols(word = col_character(),
                                     conf = col_integer(),
                                     correct = col_logical()))
  fdata %>% mutate(text_source = fparts[2],
                   font = fparts[3],
                   page = fparts[4],
                   blurring = fparts[5])
}

if (linedata) {
  sources <- Sys.glob("???")
} else {
  sources <- c("around-world",
               "best-poetry",
               "david-copperfield",
               "engineering",
               "english-church",
               "fire-prevention",
               "flatland",
               "practical-mechanics",
               "reflections",
               "supreme-court",
               "wordsworth")
}
globs <- stri_c(sources,
                stri_c(if (nchar(suffix)) "-" else "",
                       suffix, "/*-wmetrics.csv"))

if (csv_in == "") {
  wmetric_fns <- Sys.glob(globs)
  wmetric_all <- bind_rows(map(wmetric_fns, read_wmetrics))
} else {
  wmetric_all <- read_csv(csv_in)
}

if (csv_out != "") {
  write_csv(wmetric_all, csv_out)
}

summarise_wmetric_grouped <- function(w) {
  wlow <- w %>%
    filter(conf < 95) %>%
    mutate(conf_rounded = round(conf / 5) * 5) %>%
    group_by(conf_rounded, correct) %>%
    summarise(totalconf = sum(conf), count = n()) %>%
    pivot_wider(names_from = correct,
                values_from = c(totalconf, count),
                values_fill = list(totalconf = 0, count = 0)) %>%
    mutate(totalconf = totalconf_TRUE + totalconf_FALSE,
           totalcount = count_TRUE + count_FALSE,
           meanconf = totalconf / totalcount,
           truefrac = 100 * count_TRUE / totalcount) %>%
    ungroup() %>%
    select(meanconf, truefrac, totalcount)
  
  whigh <- w %>%
    filter(conf >= 95) %>%
    group_by(conf, correct) %>%
    summarise(count = n()) %>%
    pivot_wider(names_from = correct,
                values_from = count,
                values_fill = list(count = 0)) %>%
    mutate(meanconf = round(conf),
           totalcount = `TRUE` + `FALSE`,
           truefrac = 100 * `TRUE` / totalcount) %>%
    ungroup() %>%
    select(meanconf, truefrac, totalcount)
  
  bind_rows(wlow, whigh)
}

summarise_wmetric <- function(w) {
  w %>%
    group_by(conf, correct) %>%
    summarise(count = n()) %>%
    pivot_wider(names_from = correct,
                values_from = count,
                values_fill = list(count = 0)) %>%
    mutate(totalcount = `TRUE` + `FALSE`,
           truefrac = 100 * `TRUE` / totalcount)
}

summarise_wmetric_by <- function(w, doby) {
  doby <- enquo(doby)
  w %>%
    group_by(!!doby, conf, correct) %>%
    summarise(count = n()) %>%
    pivot_wider(names_from = correct,
                values_from = count,
                values_fill = list(count = 0)) %>%
    mutate(totalcount = `TRUE` + `FALSE`,
           truefrac = 100 * `TRUE` / totalcount)
}

wmetric_cnt_grouped <- summarise_wmetric_grouped(wmetric_all)
wmetric_cnt <- summarise_wmetric(wmetric_all)
wmetric_cnt_byfont <- summarise_wmetric_by(wmetric_all, font)
if (! linedata) {
  wmetric_cnt_bytext <- summarise_wmetric_by(wmetric_all, text_source)
}
wmetric_cnt_byblur <- summarise_wmetric_by(wmetric_all, blurring)

# This produces a graph of the summarised data
p <- ggplot(data = wmetric_cnt_grouped,
       mapping = aes(x = meanconf, y = truefrac)) +
  geom_point(aes(size = totalcount)) +
  geom_abline(slope = 1, intercept = 0, color = "lightgreen") +
  coord_cartesian(xlim = c(0, 102), ylim = c(0, 102)) +
  scale_x_continuous(expand = c(0, 0)) +
  scale_y_continuous(expand = c(0, 0)) +
  xlab("confidence (%)") +
  ylab("correct (%)") +
  theme(panel.grid.major = element_blank(),
        panel.grid.minor = element_blank(),
        panel.background = element_blank(),
        axis.line = element_line(colour = "black"),
        axis.title = element_text(family = "Times", size = 10),
        axis.text = element_text(family = "Times", size = 10),
        legend.position = "none")
  
ggsave("conf-correct-plot.pdf", width = 4, height = 4)

## These are some other graphs which might be informative
# ggplot(data = wmetric_cnt,
#        mapping = aes(x = conf, y = truefrac)) +
#   geom_point(aes(size = totalcount)) +
#   geom_abline(slope = 1, intercept = 0, color = "lightgreen") +
#   coord_cartesian(xlim = c(0, 100), ylim = c(0, 100))
# 
# ggplot(data = wmetric_cnt_byfont,
#        mapping = aes(x = conf, y = truefrac)) +
#   geom_point(aes(color = font)) +
#   geom_abline(slope = 1, intercept = 0, color = "lightgreen") +
#   coord_cartesian(xlim = c(0, 100), ylim = c(0, 100))
# 
# if (! linedata) {
#   ggplot(data = wmetric_cnt_bytext,
#          mapping = aes(x = conf, y = truefrac)) +
#     geom_point(aes(color = text_source)) +
#     geom_abline(slope = 1, intercept = 0, color = "lightgreen") +
#     coord_cartesian(xlim = c(0, 100), ylim = c(0, 100))
# }
# 
# ggplot(data = wmetric_cnt_byblur,
#        mapping = aes(x = conf, y = truefrac)) +
#   geom_point(aes(color = blurring)) +
#   geom_abline(slope = 1, intercept = 0, color = "lightgreen") +
#   coord_cartesian(xlim = c(0, 100), ylim = c(0, 100))
