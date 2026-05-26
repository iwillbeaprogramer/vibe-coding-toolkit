using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using StockDashboard.Wpf.Models;
using StockDashboard.Wpf.Services;

namespace StockDashboard.Wpf.ViewModels;

public partial class MainWindowViewModel : ObservableObject
{
    private static readonly Regex SymbolPattern = new("^[A-Z0-9.\\-]{1,15}$", RegexOptions.Compiled);
    public static readonly string[] AllowedRanges = { "1mo", "6mo", "1y" };

    private readonly IStockApiClient _apiClient;
    private CancellationTokenSource? _searchCts;

    public MainWindowViewModel(IStockApiClient apiClient)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));
        ChartPoints = new ObservableCollection<ChartPointDto>();
        SearchCommand = new AsyncRelayCommand(SearchAsync, CanSearch);
    }

    [ObservableProperty] private string _symbolInput = string.Empty;
    [ObservableProperty] private string _selectedRange = "6mo";
    [ObservableProperty] private bool _isBusy;
    [ObservableProperty] private string? _errorMessage;
    [ObservableProperty] private StockDetailDto? _stock;
    [ObservableProperty] private bool _hasResult;

    public ObservableCollection<ChartPointDto> ChartPoints { get; }

    public IAsyncRelayCommand SearchCommand { get; }

    partial void OnSymbolInputChanged(string value) => SearchCommand.NotifyCanExecuteChanged();
    partial void OnIsBusyChanged(bool value) => SearchCommand.NotifyCanExecuteChanged();

    private bool CanSearch() => !IsBusy && !string.IsNullOrWhiteSpace(SymbolInput);

    /// <summary>Public for unit tests: trim + upper-case + validate.</summary>
    public static (bool ok, string normalized, string? error) NormalizeSymbol(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
            return (false, string.Empty, "종목 심볼을 입력해 주세요.");
        var candidate = raw.Trim().ToUpperInvariant();
        if (candidate.Length > 15)
            return (false, candidate, "심볼은 최대 15자까지 입력할 수 있습니다.");
        if (!SymbolPattern.IsMatch(candidate))
            return (false, candidate, "영문/숫자/점(.)/하이픈(-)만 입력할 수 있습니다.");
        return (true, candidate, null);
    }

    public async Task SearchAsync()
    {
        var (ok, normalized, validationError) = NormalizeSymbol(SymbolInput);
        if (!ok)
        {
            ErrorMessage = validationError;
            HasResult = false;
            return;
        }

        if (!AllowedRanges.Contains(SelectedRange))
        {
            ErrorMessage = "지원하지 않는 차트 기간입니다.";
            return;
        }

        _searchCts?.Cancel();
        _searchCts = new CancellationTokenSource();
        var ct = _searchCts.Token;

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            var detail = await _apiClient.GetStockDetailAsync(normalized, SelectedRange, ct).ConfigureAwait(true);
            ApplyStockDetail(detail);
        }
        catch (OperationCanceledException)
        {
            // user-initiated cancel: silently drop.
        }
        catch (StockApiException ex)
        {
            HasResult = false;
            ErrorMessage = ex.StatusCode switch
            {
                404 => $"'{normalized}' 종목을 찾을 수 없습니다.",
                400 => $"입력이 올바르지 않습니다: {ex.Message}",
                502 => "데이터 공급처 오류로 일시적으로 조회가 불가능합니다. 잠시 후 다시 시도해 주세요.",
                0 => ex.Message,
                _ => $"오류({ex.StatusCode}): {ex.Message}",
            };
        }
        catch (Exception ex)
        {
            HasResult = false;
            ErrorMessage = $"예상치 못한 오류가 발생했습니다: {ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    /// <summary>Public so tests can assert post-deserialization mapping.</summary>
    public void ApplyStockDetail(StockDetailDto detail)
    {
        Stock = detail;
        // Rebuild chart-points off the UI thread before assignment; the
        // ObservableCollection is then refreshed once.
        var newPoints = detail.Chart?.Points ?? new List<ChartPointDto>();
        ChartPoints.Clear();
        foreach (var p in newPoints)
            ChartPoints.Add(p);
        HasResult = true;
    }
}
