using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace stocks_dashboard.Models
{
    public class StockDetailDto
    {
        [JsonPropertyName("symbol")] public string Symbol { get; set; } = string.Empty;
        [JsonPropertyName("name")] public string? Name { get; set; }
        [JsonPropertyName("asset_type")] public string? AssetType { get; set; }
        [JsonPropertyName("exchange")] public string? Exchange { get; set; }
        [JsonPropertyName("currency")] public string? Currency { get; set; }
        [JsonPropertyName("quote")] public StockQuoteDto Quote { get; set; } = new();
        [JsonPropertyName("fundamentals")] public StockFundamentalsDto Fundamentals { get; set; } = new();
        [JsonPropertyName("profile")] public StockProfileDto Profile { get; set; } = new();
        [JsonPropertyName("chart")] public List<ChartPointDto> Chart { get; set; } = new();
    }

    public class StockQuoteDto
    {
        [JsonPropertyName("price")] public double? Price { get; set; }
        [JsonPropertyName("previous_close")] public double? PreviousClose { get; set; }
        [JsonPropertyName("change")] public double? Change { get; set; }
        [JsonPropertyName("change_percent")] public double? ChangePercent { get; set; }
        [JsonPropertyName("open")] public double? Open { get; set; }
        [JsonPropertyName("day_high")] public double? DayHigh { get; set; }
        [JsonPropertyName("day_low")] public double? DayLow { get; set; }
        [JsonPropertyName("volume")] public long? Volume { get; set; }
        [JsonPropertyName("as_of")] public DateTime? AsOf { get; set; }
    }

    public class StockFundamentalsDto
    {
        [JsonPropertyName("market_cap")] public double? MarketCap { get; set; }
        [JsonPropertyName("pe_ratio")] public double? PeRatio { get; set; }
        [JsonPropertyName("eps")] public double? Eps { get; set; }
        [JsonPropertyName("dividend_yield")] public double? DividendYield { get; set; }
        [JsonPropertyName("fifty_two_week_high")] public double? FiftyTwoWeekHigh { get; set; }
        [JsonPropertyName("fifty_two_week_low")] public double? FiftyTwoWeekLow { get; set; }
        [JsonPropertyName("average_volume")] public long? AverageVolume { get; set; }
    }

    public class StockProfileDto
    {
        [JsonPropertyName("sector")] public string? Sector { get; set; }
        [JsonPropertyName("industry")] public string? Industry { get; set; }
        [JsonPropertyName("description")] public string? Description { get; set; }
    }

    public class ChartPointDto
    {
        [JsonPropertyName("timestamp")] public DateTime Timestamp { get; set; }
        [JsonPropertyName("open")] public double Open { get; set; }
        [JsonPropertyName("high")] public double High { get; set; }
        [JsonPropertyName("low")] public double Low { get; set; }
        [JsonPropertyName("close")] public double Close { get; set; }
        [JsonPropertyName("volume")] public long Volume { get; set; }
    }

    public class ApiErrorDto
    {
        [JsonPropertyName("code")] public string? Code { get; set; }
        [JsonPropertyName("message")] public string? Message { get; set; }
    }
}
