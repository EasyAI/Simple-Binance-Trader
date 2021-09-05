// Indicator meta details
const indicator_chart_types_mapping = {'patterns_data_lines':'line', 'patterns_data_points':'scatter', 'tops_bottoms':'scatter', 'data_lines':'line', 'cps':'line', 'ichi':'line', 'boll':'line', 'adx':'line', 'stock':'line', 'order':'scatter', 'ema':'line', 'sma':'line', 'rma':'line', 'rsi':'line', 'mfi':'line', 'cci':'line', 'zerolagmacd':'macd', 'macd':'macd'}
const indicator_home_type_mapping = {'patterns_data_lines':'MAIN', 'patterns_data_points':'MAIN', 'tops_bottoms':'MAIN', 'data_lines':'MAIN', 'ichi':'MAIN', 'cps':'MAIN', 'boll':'MAIN', 'adx':'OWN', 'stock':'OWN', 'order':'MAIN', 'ema':'MAIN', 'sma':'MAIN', 'rma':'MAIN', 'rsi':'OWN', 'mfi':'OWN', 'cci':'OWN', 'zerolagmacd':'OWN', 'macd':'OWN'}
const indicator_is_single_mapping = ['patterns_data_lines', 'patterns_data_points', 'tops_bottoms', 'data_lines', 'order', 'ema', 'sma', 'rma', 'rsi', 'mfi', 'cci', 'cps']
const double_depth_indicators = ['ema', 'sma', 'order', 'patterns_data_points', 'patterns_data_lines'];

// Base Apex chart configuration.
window.Apex = {
    chart: {
        animations: {
            enabled: false
        }
    },
    autoScaleYaxis: false
};

// Chart template for main chart.
var base_candle_chart_configuration = {
    series: [],
    chart: {
        height: 800,
        id: 'main_Chart',
        type: 'line'
    },
    fill: {
        type:'solid',
    },
    markers: {
        size: []
    },
    //colors: [],
    stroke: {
        width: []
    },
    tooltip: {
        shared: true,
        custom: []
    },
    xaxis: {
        type: 'datetime',
    },
    yaxis: {
        labels: {
            minWidth: 40,
            formatter: function (value) { return Math.round(value); }
        },
    }
};

let loaded_candles_chart = null;


function initial_build(target_element, charting_data) {
    // Add main chandle chart position.
    var candle_data = charting_data['candles'];
    var indicator_data = charting_data['indicators'];
    var main_chart_series = [];

    loaded_candles_chart = JSON.parse(JSON.stringify(base_candle_chart_configuration));

    populate_chart(indicator_data);

    var built_data = build_candle_data(candle_data);
    var built_candle_data = built_data[0];

    // Finally add the candle to the displayed chart.
    loaded_candles_chart["series"].push({
        name: 'candle',
        type: 'candlestick',
        data: built_candle_data
    });
    loaded_candles_chart["stroke"]["width"].push(1);
    loaded_candles_chart["markers"]["size"].push(0);
    loaded_candles_chart["tooltip"]["custom"].push(function({seriesIndex, dataPointIndex, w}) {
        var o = w.globals.seriesCandleO[seriesIndex][dataPointIndex]
        var h = w.globals.seriesCandleH[seriesIndex][dataPointIndex]
        var l = w.globals.seriesCandleL[seriesIndex][dataPointIndex]
        var c = w.globals.seriesCandleC[seriesIndex][dataPointIndex]
        return (`Open:${o}<br>High:${h}<br>Low:${l}<br>Close:${c}`)
    });

    candle_chart = new ApexCharts(target_element, loaded_candles_chart);
    candle_chart.render();
}


function build_candle_data(candle_data) {
    var built_candle_data = [];
    var built_volume_data = [];

    for (var i=0; i < candle_data.length; i++) {
        var candle = candle_data[i];
        built_candle_data.push({
            x: new Date(parseInt(candle[0])),
            y: [
                candle[1],
                candle[2],
                candle[3],
                candle[4]
            ]
        });

        built_volume_data.push({
            x: new Date(parseInt(candle[0])),
            y: Math.round(candle[5])
        });
    }
    return([built_candle_data, built_volume_data]);
}


function build_timeseries(ind_obj) {
    var indicator_lines = [];
    var keys = []

    // Use sorted timestamp to print out.
    for (var ind in ind_obj) {
        var current_set = ind_obj[ind]

        if (typeof current_set[0] == 'number') {
            indicator_lines.push({
                x: new Date(parseInt(current_set[0])),
                y: current_set[1].toFixed(8)
            });
        } else {
            for (var sub_ind in current_set) {
                if (!keys.includes(sub_ind)) {
                    keys.push(sub_ind)
                    indicator_lines[sub_ind] = []
                }
                indicator_lines[sub_ind].push({
                    x: new Date(parseInt(current_set[sub_ind][0])),
                    y: current_set[sub_ind][1].toFixed(8)
                });
            }
        }
    }
    return(indicator_lines);
}


function build_basic_indicator(chart_obj, ind_obj, chart_type, line_name=null, ind_name=null) {
    var indicator_lines = build_timeseries(ind_obj);

    if (!(line_name == null)) {
        chart_obj["series"].push({
            name: line_name,
            type: chart_type,
            data: indicator_lines
        });
        if (chart_type == "scatter") {
            chart_obj["stroke"]["width"].push(2);
            chart_obj["markers"]["size"].push(8);
        } else {
            chart_obj["stroke"]["width"].push(2);
            chart_obj["markers"]["size"].push(0);
        }
    } else {
        for (var sub_ind_name in indicator_lines) {
            chart_obj["series"].push({
                name: sub_ind_name,
                type: chart_type,
                data: indicator_lines[sub_ind_name]});
            if (chart_type == "scatter") {
                chart_obj["stroke"]["width"].push(2);
                chart_obj["markers"]["size"].push(8);
            } else {
                chart_obj["stroke"]["width"].push(2);
                chart_obj["markers"]["size"].push(0);
            }
        }
    }

    if ('custom' in chart_obj["tooltip"]) {
        if (!(line_name == null)) {
            chart_obj["tooltip"]["custom"].push(
                function({seriesIndex, dataPointIndex, w}) {
                    return w.globals.series[seriesIndex][dataPointIndex]
            });
        } else {
            for (var ind in indicator_lines) {
                chart_obj["tooltip"]["custom"].push(
                    function({seriesIndex, dataPointIndex, w}) {
                        return w.globals.series[seriesIndex][dataPointIndex]
                });
            }
        }
    }
}


function populate_chart(indicator_data) {

    for (var raw_indicator in indicator_data) {

        var patt = /[^\d]+/i;
        var indicator = raw_indicator.match(patt)[0];

        var current_ind = indicator_data[raw_indicator];
        var chart_type = indicator_chart_types_mapping[indicator];
        var home_chart = indicator_home_type_mapping[indicator];
        var line_name = null;
        var ind_name = null;

        if (home_chart == "MAIN") {
            target_chart = loaded_candles_chart;

            if (double_depth_indicators.includes(indicator)) {
                for (var sub_ind in current_ind) {
                    line_name = sub_ind;
                    var built_chart = build_basic_indicator(target_chart, current_ind[sub_ind], chart_type, line_name, ind_name);
                }
            } else {
                if (indicator_is_single_mapping.includes(indicator)) {
                    line_name = raw_indicator;
                }
                var built_chart = build_basic_indicator(target_chart, current_ind, chart_type, line_name, ind_name);
            }
        }
    }
}