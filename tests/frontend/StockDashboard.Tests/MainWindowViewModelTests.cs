using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using StockDashboard.Wpf.Models;
using StockDashboard.Wpf.Services;
using StockDashboard.Wpf.ViewModels;
using Xunit;

namespace StockDashboard.Tests;

public class MainWindowViewModelTests
{
    private sealed class FakeApiClient : IStockApiClient
    {
        public string? LastSymbol { get; private set; }
        public string? LastRange { get; private set; }
        public StockDetailDto? Response { get; set; }
        public Exception? ToThrow { get; set; }

        public Task<StockDetailDto> GetStockDetailAsync(string symbol, string range, CancellationToken ct = default)
        {
            LastSymbol = symbol;
            LastRange = range;
            if (ToThrow != null) throw ToThrow;
            return Task.FromResult(Response ?? new StockDetailDto { Symbol = symbol });
        }
    }

    [Theory]
    [InlineData("  qld ", true, "QLD", null)]
    [InlineData("Qld", true, "QLD", null)]
    [InlineData("BRK-B", true, "BRK-B", null)]
    [InlineData("BF.B", true, "BF.B", null)]
    public void NormalizeSymbol_AcceptsValidInput(string input, bool ok, string normalized, string? err)
    {
        var (got_ok, got_norm, got_err) = MainWindowViewModel.NormalizeSymbol(input);
        Assert.Equal(ok, got_ok);
        Assert.Equal(normalized, got_norm);
        Assert.Equal(err, got_err);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("AA!PL")]
    [InlineData("AAAAAAAAAAAAAAAA")] // 16 chars
    [InlineData("hello world")]
    public void NormalizeSymbol_RejectsInvalidInput(string input)
    {
        var (ok, _, err) = MainWindowViewModel.NormalizeSymbol(input);
        Assert.False(ok);
        Assert.False(string.IsNullOrEmpty(err));
    }

    [Fact]
    public async Task SearchAsync_SetsErrorMessage_WhenInputInvalid()
    {
        var vm = new MainWindowViewModel(new FakeApiClient()) { SymbolInput = "!!!" };
        await vm.SearchAsync();
        Assert.False(vm.HasResult);
        Assert.False(string.IsNullOrEmpty(vm.ErrorMessage));
    }

    [Fact]
    public async Task SearchAsync_PopulatesStock_OnSuccess()
    {
        var dto = new StockDetailDto
        {
            Symbol = "QLD",
            Name = "Test ETF",
            Quote = new QuoteDto { Price = 100.0, PreviousClose = 95.0, Change = 5.0, ChangePercent = 5.26 },
            Chart = new ChartDto
            {
                Range = "6mo",
                Points = new List<ChartPointDto>
                {
                    new() { Date = "2026-01-01", Close = 90.0 },
                    new() { Date = "2026-01-02", Close = 91.5 },
                },
            },
        };
        var fake = new FakeApiClient { Response = dto };
        var vm = new MainWindowViewModel(fake) { SymbolInput = " qld " };

        await vm.SearchAsync();

        Assert.Equal("QLD", fake.LastSymbol);
        Assert.Equal("6mo", fake.LastRange);
        Assert.True(vm.HasResult);
        Assert.Null(vm.ErrorMessage);
        Assert.NotNull(vm.Stock);
        Assert.Equal("QLD", vm.Stock!.Symbol);
        Assert.Equal(2, vm.ChartPoints.Count);
    }

    [Fact]
    public async Task SearchAsync_HandlesNotFoundResponse()
    {
        var fake = new FakeApiClient { ToThrow = new StockApiException(404, "symbol_not_found", "not found") };
        var vm = new MainWindowViewModel(fake) { SymbolInput = "ZZZZ" };

        await vm.SearchAsync();

        Assert.False(vm.HasResult);
        Assert.Contains("찾을 수 없습니다", vm.ErrorMessage);
    }

    [Fact]
    public async Task SearchAsync_HandlesUpstreamFailure()
    {
        var fake = new FakeApiClient { ToThrow = new StockApiException(502, "upstream_data_error", "upstream") };
        var vm = new MainWindowViewModel(fake) { SymbolInput = "QLD" };

        await vm.SearchAsync();

        Assert.False(vm.HasResult);
        Assert.Contains("일시적", vm.ErrorMessage);
    }

    [Fact]
    public async Task SearchAsync_HandlesNetworkError()
    {
        var fake = new FakeApiClient { ToThrow = new StockApiException(0, "network_error", "connection refused") };
        var vm = new MainWindowViewModel(fake) { SymbolInput = "QLD" };

        await vm.SearchAsync();

        Assert.False(vm.HasResult);
        Assert.Equal("connection refused", vm.ErrorMessage);
    }

    [Fact]
    public async Task SearchAsync_UserCancellation_DoesNotSurfaceErrorMessage()
    {
        // When the user re-types quickly, the prior in-flight request is cancelled
        // and the API client throws OperationCanceledException. The ViewModel must
        // swallow it silently — no error banner, no HasResult flip.
        var fake = new FakeApiClient
        {
            ToThrow = new OperationCanceledException("user cancelled"),
        };
        var vm = new MainWindowViewModel(fake) { SymbolInput = "QLD" };

        await vm.SearchAsync();

        Assert.Null(vm.ErrorMessage);
        Assert.False(vm.HasResult);
        Assert.False(vm.IsBusy);
    }

    [Fact]
    public void SearchCommand_DisabledWhenSymbolEmpty()
    {
        var vm = new MainWindowViewModel(new FakeApiClient());
        Assert.False(vm.SearchCommand.CanExecute(null));
        vm.SymbolInput = "QLD";
        Assert.True(vm.SearchCommand.CanExecute(null));
    }
}
