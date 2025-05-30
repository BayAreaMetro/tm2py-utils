# Utility script to convert standard CSV to DBF

library(foreign)

F_INPUT  = "blocks_mazs_tazs.csv"
F_OUTPUT = "blocks_mazs_tazs.dbf"

data_df <- read.table(file = F_INPUT, header = TRUE, sep = ",", stringsAsFactors = FALSE,
                      colClasses=c("GEOID10"="character"))

write.dbf(data_df, F_OUTPUT, factor2char = TRUE, max_nchar = 254)
