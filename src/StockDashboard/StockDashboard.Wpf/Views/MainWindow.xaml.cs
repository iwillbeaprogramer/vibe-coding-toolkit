using System.ComponentModel;
using System.Linq;
using System.Windows;
using LiveChartsCore;
using LiveChartsCore.SkiaSharpView;
using LiveChartsCore.SkiaSharpView.Painting;
using SkiaSharp;
using StockDashboard.Wpf.Services;
using StockDashboard.Wpf.ViewModels;

namespace StockDashboard.Wpf.Views;

public partial class MainWindow : Window
{
    private readonly MainWindowViewModel _viewModel;

    public MainWindow()
    {
        InitializeComponent();
        _viewModel = new MainWindowViewModel(new StockApiClient());
        DataContext = _viewModel;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(MainWindowViewModel.HasResult) && _viewModel.HasResult)
        {
            RefreshChart();
        }
    }

    private void RefreshChart()
    {
        var points = _viewModel.ChartPoints
            .Where(p => p.Close.HasValue)
            .Select(p => p.Close!.Value)
            .ToArray();

        var labels = _viewModel.ChartPoints.Select(p => p.Date).ToArray();

        var series = new ISeries[]
        {
            new LineSeries<double>
            {
                Values = points,
                GeometrySize = 0,
                LineSmoothness = 0.5,
                Fill = new LinearGradientPaint(
                    new[] { new SKColor(108, 142, 245, 160), new SKColor(108, 142, 245, 0) },
                    new SKPoint(0.5f, 0), new SKPoint(0.5f, 1)),
                Stroke = new SolidColorPaint(new SKColor(108, 142, 245)) { StrokeThickness = 2 },
                Name = _viewModel.Stock?.Symbol ?? string.Empty,
            },
        };

        PriceChart.Series = series;
        PriceChart.XAxes = new[]
        {
            new Axis
            {
                Labels = labels,
                LabelsRotation = -25,
                TextSize = 10,
                LabelsPaint = new SolidColorPaint(new SKColor(138, 147, 166)),
            },
        };
        PriceChart.YAxes = new[]
        {
            new Axis
            {
                TextSize = 10,
                LabelsPaint = new SolidColorPaint(new SKColor(138, 147, 166)),
            },
        };
    }
}
