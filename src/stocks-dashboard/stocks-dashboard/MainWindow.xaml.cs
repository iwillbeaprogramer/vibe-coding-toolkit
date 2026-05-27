using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using ScottPlot;
using stocks_dashboard.Models;
using stocks_dashboard.Services;

namespace stocks_dashboard
{
    public partial class MainWindow : Window
    {
        private readonly StockApiClient _apiClient = new();
        private CancellationTokenSource? _cts;
        private bool _isBusy;

        public MainWindow()
        {
            InitializeComponent();
            PriceChart.Plot.Title("");
            PriceChart.Refresh();
        }

        private async void SearchButton_Click(object sender, RoutedEventArgs e)
        {
            await RunSearchAsync();
        }

        private async void SymbolTextBox_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Enter)
            {
                e.Handled = true;
                await RunSearchAsync();
            }
        }

        private async Task RunSearchAsync()
        {
            if (_isBusy)
            {
                return;
            }

            var raw = SymbolTextBox.Text ?? string.Empty;
            var symbol = raw.Trim().ToUpperInvariant();
            if (string.IsNullOrEmpty(symbol))
            {
                SetStatus("종목 코드를 입력해 주세요.", isError: true);
                return;
            }

            _cts?.Cancel();
            _cts = new CancellationTokenSource();

            try
            {
                SetBusy(true);
                SetStatus($"'{symbol}' 조회 중...", isError: false);

                var detail = await _apiClient.FetchStockAsync(symbol, _cts.Token).ConfigureAwait(true);
                RenderDetail(detail);
                SetStatus($"'{symbol}' 조회 완료.", isError: false);
            }
            catch (OperationCanceledException)
            {
                SetStatus("이전 요청이 취소되었습니다.", isError: false);
            }
            catch (StockApiException ex)
            {
                SetStatus(ex.UserMessage, isError: true);
            }
            catch (Exception ex)
            {
                SetStatus($"예기치 못한 오류: {ex.Message}", isError: true);
            }
            finally
            {
                SetBusy(false);
            }
        }

        private void SetBusy(bool isBusy)
        {
            _isBusy = isBusy;
            LoadingOverlay.Visibility = isBusy ? Visibility.Visible : Visibility.Collapsed;
            SearchButton.IsEnabled = !isBusy;
            LoadingIndicator.Text = isBusy ? "로딩 중" : "대기 중";
        }

        private void SetStatus(string message, bool isError)
        {
            StatusMessage.Text = message;
            StatusMessage.Foreground = isError
                ? System.Windows.Media.Brushes.IndianRed
                : System.Windows.Media.Brushes.LightGray;
        }

        private void RenderDetail(StockDetailDto detail)
        {
            NameTextBlock.Text = detail.Name ?? detail.Symbol;
            SymbolTextBlock.Text = $"{detail.Symbol} · {Display(detail.Exchange)} · {Display(detail.Currency)}";

            PriceTextBlock.Text = FormatPrice(detail.Quote.Price, detail.Currency);
            ChangeTextBlock.Text = FormatChange(detail.Quote.Change, detail.Quote.ChangePercent);
            ChangeTextBlock.Foreground = (detail.Quote.Change ?? 0) >= 0
                ? System.Windows.Media.Brushes.LimeGreen
                : System.Windows.Media.Brushes.OrangeRed;

            QuotePrice.Text = FormatPrice(detail.Quote.Price, detail.Currency);
            QuotePrevClose.Text = FormatPrice(detail.Quote.PreviousClose, detail.Currency);
            QuoteOpen.Text = FormatPrice(detail.Quote.Open, detail.Currency);
            QuoteHigh.Text = FormatPrice(detail.Quote.DayHigh, detail.Currency);
            QuoteLow.Text = FormatPrice(detail.Quote.DayLow, detail.Currency);
            QuoteVolume.Text = FormatLong(detail.Quote.Volume);
            QuoteAvgVolume.Text = FormatLong(detail.Fundamentals.AverageVolume);
            QuoteAsOf.Text = detail.Quote.AsOf?.ToLocalTime().ToString("yyyy-MM-dd HH:mm") ?? "N/A";

            FundMarketCap.Text = FormatLargeNumber(detail.Fundamentals.MarketCap);
            FundPE.Text = FormatDouble(detail.Fundamentals.PeRatio);
            FundEPS.Text = FormatDouble(detail.Fundamentals.Eps);
            FundDividendYield.Text = FormatPercent(detail.Fundamentals.DividendYield);
            Fund52High.Text = FormatPrice(detail.Fundamentals.FiftyTwoWeekHigh, detail.Currency);
            Fund52Low.Text = FormatPrice(detail.Fundamentals.FiftyTwoWeekLow, detail.Currency);

            ProfileAssetType.Text = Display(detail.AssetType);
            ProfileSector.Text = Display(detail.Profile.Sector);
            ProfileIndustry.Text = Display(detail.Profile.Industry);
            ProfileDescription.Text = Display(detail.Profile.Description);

            RenderChart(detail);
        }

        private void RenderChart(StockDetailDto detail)
        {
            var plot = PriceChart.Plot;
            plot.Clear();

            if (detail.Chart.Count == 0)
            {
                ChartPlaceholder.Visibility = Visibility.Visible;
                PriceChart.Refresh();
                return;
            }

            ChartPlaceholder.Visibility = Visibility.Collapsed;

            var candles = detail.Chart
                .Select(p => new OHLC(p.Open, p.High, p.Low, p.Close, p.Timestamp, TimeSpan.FromDays(1)))
                .ToList();

            plot.Add.Candlestick(candles);

            plot.Axes.DateTimeTicksBottom();
            plot.Title($"{detail.Symbol} - {detail.Name}");
            plot.YLabel($"가격 ({detail.Currency ?? ""})");
            plot.Axes.AutoScale();
            PriceChart.Refresh();
        }

        private static string Display(string? value) => string.IsNullOrWhiteSpace(value) ? "N/A" : value!;

        private static string FormatPrice(double? value, string? currency)
        {
            if (value is null)
            {
                return "N/A";
            }
            var symbol = currency == "USD" ? "$" : "";
            return $"{symbol}{value.Value:N2}";
        }

        private static string FormatChange(double? change, double? percent)
        {
            if (change is null && percent is null)
            {
                return "N/A";
            }
            var sign = (change ?? 0) >= 0 ? "+" : "";
            var changeText = change.HasValue ? $"{sign}{change.Value:N2}" : "N/A";
            var pctText = percent.HasValue ? $"{sign}{percent.Value:N2}%" : "N/A";
            return $"{changeText}  ({pctText})";
        }

        private static string FormatDouble(double? value) =>
            value.HasValue ? value.Value.ToString("N2") : "N/A";

        private static string FormatPercent(double? value) =>
            value.HasValue ? (value.Value * 100).ToString("N2") + "%" : "N/A";

        private static string FormatLong(long? value) =>
            value.HasValue ? value.Value.ToString("N0") : "N/A";

        private static string FormatLargeNumber(double? value)
        {
            if (!value.HasValue)
            {
                return "N/A";
            }
            var v = value.Value;
            if (v >= 1_000_000_000_000) return $"{v / 1_000_000_000_000:N2}T";
            if (v >= 1_000_000_000) return $"{v / 1_000_000_000:N2}B";
            if (v >= 1_000_000) return $"{v / 1_000_000:N2}M";
            return v.ToString("N0");
        }
    }
}
