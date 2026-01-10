# =============================================================================
# Understanding Linear Regression with Bitcoin Data
# =============================================================================
# A step-by-step tutorial using MVRV to predict forward returns
#
# Run each section one at a time (Cmd+Enter on Mac, Ctrl+Enter on Windows)
# =============================================================================

# Load packages
library(tidyverse)
library(arrow)  # For reading parquet files

# =============================================================================
# PART 1: LOAD DATA
# =============================================================================

# Set your data directory
DATA_DIR <- "~/Documents/bitcoin-lab-btc-data-pipeline/data/raw"

# Load MVRV and price
mvrv_raw <- read_parquet(file.path(DATA_DIR, "mvrv.parquet"))
price_raw <- read_parquet(file.path(DATA_DIR, "price.parquet"))

# Look at the data
head(mvrv_raw)
head(price_raw)

# Rename columns and join
mvrv <- mvrv_raw %>% 
  rename(mvrv = value)

price <- price_raw %>% 
  rename(price = value)

# Join into single dataframe
df <- mvrv %>%
  inner_join(price, by = "time") %>%
  arrange(time)

# Check it
glimpse(df)

# =============================================================================
# PART 2: CREATE FORWARD RETURNS (Y variable)
# =============================================================================

# We want to predict: "If MVRV is X today, what will returns be in 30 days?"
# 
# Y = (price in 30 days - price today) / price today

df <- df %>%
  mutate(
    # Forward price (30 days ahead)
    price_fwd = lead(price, 30),
    
    # Forward return (what we're trying to predict)
    fwd_return = (price_fwd - price) / price
  )

# Check - we should have NAs at the end (no future data)
tail(df, 35)

# =============================================================================
# PART 3: VISUALISE THE RELATIONSHIP
# =============================================================================

# First, let's just plot MVRV vs forward returns
# Does it look like there's a relationship?

ggplot(df, aes(x = mvrv, y = fwd_return)) +
  geom_point(alpha = 0.3, size = 0.5) +
  geom_smooth(method = "lm", color = "red", se = TRUE) +
  labs(
    title = "MVRV vs 30-Day Forward Returns",
    subtitle = "Each dot = one day. Red line = best fit regression line.",
    x = "MVRV (today)",
    y = "30-Day Forward Return"
  ) +
  theme_minimal() +
  scale_y_continuous(labels = scales::percent)

# What do you see?
# - Lots of scatter (noise) - that's normal for financial data
# - The red line shows the average relationship
# - The grey band shows uncertainty (confidence interval)

# =============================================================================
# PART 4: RUN THE REGRESSION
# =============================================================================

# The regression model is:
#   fwd_return = α + β * mvrv + ε
#
# Where:
#   α (alpha) = intercept (return when MVRV = 0)
#   β (beta)  = coefficient (how much return changes per unit MVRV)
#   ε (epsilon) = error (what we can't explain)

# Fit the model
model <- lm(fwd_return ~ mvrv, data = df)

# View the results
summary(model)

# =============================================================================
# PART 5: UNDERSTANDING THE OUTPUT
# =============================================================================

# Let's break down what summary(model) tells us:
#
# COEFFICIENTS:
#              Estimate  Std. Error  t value   Pr(>|t|)
# (Intercept)  0.0XXX    0.0XXX      X.XX      0.XXXX
# mvrv         0.0XXX    0.0XXX      X.XX      0.XXXX   ***
#
# Key things to look at:

# 1. COEFFICIENT (Estimate for 'mvrv')
coef(model)["mvrv"]
# Interpretation: For each 1-unit increase in MVRV, forward return changes by this much
# Positive = higher MVRV predicts higher returns
# Negative = higher MVRV predicts lower returns

# 2. P-VALUE (Pr(>|t|) for 'mvrv')
summary(model)$coefficients["mvrv", "Pr(>|t|)"]
# Interpretation: Probability this relationship is just random noise
# p < 0.05 = statistically significant (real signal)
# p > 0.05 = could be noise

# 3. R-SQUARED
summary(model)$r.squared
# Interpretation: What % of return variance does MVRV explain?
# 0.01 (1%) is actually decent for financial data!
# 0.05 (5%) would be very good

# 4. T-STATISTIC
summary(model)$coefficients["mvrv", "t value"]
# Interpretation: coefficient / standard error
# |t| > 2 usually means significant

# =============================================================================
# PART 6: VISUALISE THE REGRESSION RESULTS
# =============================================================================

# Let's make this clearer with a nicer plot

# Add predictions to our data
df <- df %>%
  mutate(
    predicted = predict(model, newdata = df),
    residual = fwd_return - predicted
  )

# Plot actual vs predicted
ggplot(df, aes(x = mvrv, y = fwd_return)) +
  geom_point(alpha = 0.2, size = 0.5, color = "gray50") +
  geom_line(aes(y = predicted), color = "red", size = 1) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "gray70") +
  labs(
    title = "MVRV Regression: Actual vs Predicted",
    subtitle = sprintf(
      "R² = %.3f | p-value = %.4f | Coefficient = %.4f",
      summary(model)$r.squared,
      summary(model)$coefficients["mvrv", "Pr(>|t|)"],
      coef(model)["mvrv"]
    ),
    x = "MVRV",
    y = "30-Day Forward Return"
  ) +
  theme_minimal() +
  scale_y_continuous(labels = scales::percent, limits = c(-0.5, 1))

# =============================================================================
# PART 7: RESIDUALS (What the model can't explain)
# =============================================================================

# Good residuals should:
# 1. Be centered around 0
# 2. Have no pattern (random scatter)
# 3. Have roughly constant spread

# Residuals plot
ggplot(df, aes(x = mvrv, y = residual)) +
  geom_point(alpha = 0.2, size = 0.5) +
  geom_hline(yintercept = 0, color = "red", linetype = "dashed") +
  labs(
    title = "Residuals: What MVRV Can't Explain",
    subtitle = "Should be random scatter around 0",
    x = "MVRV",
    y = "Residual (Actual - Predicted)"
  ) +
  theme_minimal() +
  scale_y_continuous(labels = scales::percent)

# Histogram of residuals (should be roughly normal)
ggplot(df, aes(x = residual)) +
  geom_histogram(bins = 50, fill = "steelblue", alpha = 0.7) +
  geom_vline(xintercept = 0, color = "red", linetype = "dashed") +
  labs(
    title = "Distribution of Residuals",
    subtitle = "Should be roughly bell-shaped around 0",
    x = "Residual",
    y = "Count"
  ) +
  theme_minimal()

# =============================================================================
# PART 8: CONFIDENCE INTERVALS
# =============================================================================

# How confident are we in our coefficient estimate?

confint(model, level = 0.95)

# This gives you the 95% confidence interval for each coefficient
# For mvrv: we're 95% confident the true coefficient is between [lower, upper]
# If this interval contains 0, the effect might not be real!

# Visualise confidence interval for coefficient
coef_data <- tibble(
  term = "MVRV coefficient",
  estimate = coef(model)["mvrv"],
  conf.low = confint(model)["mvrv", 1],
  conf.high = confint(model)["mvrv", 2]
)

ggplot(coef_data, aes(x = term, y = estimate)) +
  geom_point(size = 4) +
  geom_errorbar(aes(ymin = conf.low, ymax = conf.high), width = 0.1) +
  geom_hline(yintercept = 0, linetype = "dashed", color = "red") +
  labs(
    title = "MVRV Coefficient with 95% Confidence Interval",
    subtitle = "If the interval crosses 0, the effect might not be real",
    x = "",
    y = "Coefficient Value"
  ) +
  theme_minimal() +
  coord_flip()

# =============================================================================
# PART 9: BULL MARKET ONLY
# =============================================================================

# Your signals are regime-specific, so let's filter to bull markets

# Define bull market periods
bull_periods <- tribble(
  ~name, ~start, ~end,
  "2015-2017", "2015-10-01", "2017-12-17",
  "2019", "2018-12-15", "2019-06-26",
  "2020-2021", "2020-03-13", "2021-11-10",
  "2023-2024", "2022-11-21", "2024-03-14",
  "2024-Present", "2024-09-01", "2026-12-31"
) %>%
  mutate(
    start = as.POSIXct(start, tz = "UTC"),
    end = as.POSIXct(end, tz = "UTC")
  )

# Function to check if a date is in a bull market
is_bull <- function(date) {
  any(map_lgl(1:nrow(bull_periods), ~ date >= bull_periods$start[.x] & date < bull_periods$end[.x]))
}

# Add regime column
df <- df %>%
  mutate(regime = if_else(map_lgl(time, is_bull), "bull", "other"))

# Check distribution
df %>% count(regime)

# Filter to bull markets only
df_bull <- df %>% filter(regime == "bull")

# Run regression on bull markets only
model_bull <- lm(fwd_return ~ mvrv, data = df_bull)
summary(model_bull)

# Compare all data vs bull only
cat("\n=== COMPARISON ===\n")
cat("\nAll Data:\n")
cat(sprintf("  Coefficient: %.5f\n", coef(model)["mvrv"]))
cat(sprintf("  p-value: %.4f\n", summary(model)$coefficients["mvrv", "Pr(>|t|)"]))
cat(sprintf("  R-squared: %.4f\n", summary(model)$r.squared))

cat("\nBull Markets Only:\n")
cat(sprintf("  Coefficient: %.5f\n", coef(model_bull)["mvrv"]))
cat(sprintf("  p-value: %.4f\n", summary(model_bull)$coefficients["mvrv", "Pr(>|t|)"]))
cat(sprintf("  R-squared: %.4f\n", summary(model_bull)$r.squared))

# =============================================================================
# PART 10: VISUALISE BOTH REGIMES
# =============================================================================

ggplot(df %>% filter(!is.na(fwd_return)), aes(x = mvrv, y = fwd_return, color = regime)) +
  geom_point(alpha = 0.3, size = 0.5) +
  geom_smooth(method = "lm", se = TRUE) +
  labs(
    title = "MVRV vs Forward Returns by Regime",
    subtitle = "The relationship might differ between bull and bear markets",
    x = "MVRV",
    y = "30-Day Forward Return",
    color = "Regime"
  ) +
  theme_minimal() +
  scale_y_continuous(labels = scales::percent, limits = c(-0.5, 1)) +
  scale_color_manual(values = c("bull" = "forestgreen", "other" = "gray50"))

# =============================================================================
# SUMMARY: WHAT TO LOOK FOR
# =============================================================================

cat("\n")
cat("=======================================================\n")
cat("SUMMARY: KEY STATISTICS FOR TRADING SIGNALS\n")
cat("=======================================================\n")
cat("\n")
cat("1. P-VALUE < 0.05 = Statistically significant\n")
cat("   Your MVRV p-value: ", sprintf("%.4f", summary(model_bull)$coefficients["mvrv", "Pr(>|t|)"]), "\n")
cat("   ", if(summary(model_bull)$coefficients["mvrv", "Pr(>|t|)"] < 0.05) "✓ SIGNIFICANT" else "✗ NOT SIGNIFICANT", "\n")
cat("\n")
cat("2. COEFFICIENT SIGN tells you direction:\n")
cat("   Your MVRV coefficient: ", sprintf("%.5f", coef(model_bull)["mvrv"]), "\n")
cat("   ", if(coef(model_bull)["mvrv"] > 0) "→ Use ABOVE threshold" else "→ Use BELOW threshold", "\n")
cat("\n")
cat("3. R-SQUARED > 0.01 is decent for finance:\n")
cat("   Your MVRV R²: ", sprintf("%.4f (%.2f%%)", summary(model_bull)$r.squared, summary(model_bull)$r.squared * 100), "\n")
cat("   ", if(summary(model_bull)$r.squared > 0.01) "✓ DECENT" else "✗ LOW", "\n")
cat("\n")
cat("=======================================================\n")
