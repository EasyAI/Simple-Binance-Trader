//
// 
var socket = io('http://'+ip+':'+port);
var xmlhttp = new XMLHttpRequest();


/*
calls 
{action=delete, data={'target':marketToDelete}
{action=forceBuy, data={'target':marketToForceBuy}
{action=forceSell, data={'target':marketToForceSell}
{action=addNewMarket, data={'target':marketToAdd}
{action=PauseTrading, data={'target':marketToPause}}
*/


// Create Trader Obhect: Represents the structure of a trader and its data.

// UI Class (user screen interaction, drawing trader data)

// Allow user interaction with a rest style api

// Allow the use of sockets for live trader updates


var xmlhttp = new XMLHttpRequest();

$(document).ready(function() {

    socket.on('current_traders_data', function(data) {
        build_results_table(data);
    });
});


function build_results_table(data) {

    var list = document.querySelector('#results-list');

    list.innerHTML = "";

    outcome = data['data']['topData'];

    row = document.createElement('tr');
    row.setAttribute('id', 'overall-section');

    row.innerHTML = `<td></td><td>Trades Done: ${outcome['oTrades']} | Outcome: ${Math.round(outcome['oTotal']*100000000)/100000000}</td>`;

    list.appendChild(row);

    currentTraders = data['data']['traders'];
    console.log(currentTraders);

    for (i = 0; i < (currentTraders.length); i++){
        row = document.createElement('tr');
        row.setAttribute('id', 'trader-section');

        current = currentTraders[i];

        market_pair = current['market'];
        overall = current['traderStats']['overall'];

        var short_stats_string = '';
        var long_stats_string = '';

        if (current['tradeInfo']['long_order_type']['S'] == null){
            long_stats_string  = `Long BUY | Type:${current['tradeInfo']['long_order_type']['B']} | Status:${current['tradeInfo']['long_order_status']['B']} | Buy Price:${current['tradeInfo']['buy_price']['long']}`;
        } else if (current['tradeInfo']['long_order_type']['S'] != null) {
            long_stats_string  = `Long SELL | Type:${current['tradeInfo']['long_order_type']['S']} | Status:${current['tradeInfo']['long_order_status']['S']} | Buy Price:${current['tradeInfo']['buy_price']['long']} | Sell Price:${current['tradeInfo']['sell_price']['long']}`;
        }

        if (current['tradeInfo']['short_order_type']['S'] == null){
            short_stats_string  = `Short BUY | Type:${current['tradeInfo']['short_order_type']['B']} | Status:${current['tradeInfo']['short_order_status']['B']} | Buy Price:${current['tradeInfo']['buy_price']['short']}`;
        } else if (current['tradeInfo']['short_order_type']['S'] != null) {
            short_stats_string  = `Short SELL | Type:${current['tradeInfo']['short_order_type']['S']} | Status:${current['tradeInfo']['short_order_status']['S']} | Buy Price:${current['tradeInfo']['buy_price']['short']} | Sell Price:${current['tradeInfo']['sell_price']['short']}`;
        }

        if (short_stats_string != '') {
            total_price_string = `${long_stats_string}<br>${short_stats_string}`;
        } else {
            total_price_string = long_stats_string;
        }
     
        buttonStart     = `<a href=# class="small-button green-button" onclick="start_trader(event, '${market_pair}');">Start</a>`;
        buttonPause     = `<a href=# class="small-button amber-button" onclick="pause_trader(event, '${market_pair}');">Pause</a>`;
        buttonRemove    = `<a href=# class="small-button red-button" onclick="delete_trader(event, '${market_pair}');">Remove</a>`;

        row.innerHTML   = `
            <td id="market-pair">${market_pair}</td>
            <td id="main-data">State: ${current['traderStats']['runtime_state']} | Trades: L:${current['traderStats']['#Trades']['long']}, S:${current['traderStats']['#Trades']['short']} | Overall: L:${Math.round(current['traderStats']['overall']['long']*100000000)/100000000}, S:${Math.round(current['traderStats']['overall']['short']*100000000)/100000000} | Last Update: ${current['traderStats']['last_update_time']} | Last Price: ${current['prices']['lastPrice']}<br>
            ${total_price_string}</td>
            <td id="remove-button">${buttonStart} ${buttonPause} ${buttonRemove}</td>
            `;

        list.appendChild(row);
    }

    buttonAdd = `<a href=# class="small-button blue-button" onclick="add_trader(event);">+</a>`;
    row = document.createElement('tr');
    row.innerHTML = `<td id="market-pair">${buttonAdd}</td>`;
    list.appendChild(row);
}


function start_trader(e, market_pair){
    e.preventDefault();
    
    console.log('Started Market ID: '+market_pair);
    rest_api('POST', 'trader_update', {'action':'start', 'market':market_pair});
}


function pause_trader(e, market_pair){
    e.preventDefault();
    
    console.log('Paused Market: '+market_pair);
    rest_api('POST', 'trader_update', {'action':'pause', 'market':market_pair});
}


function delete_trader(e, market_pair){
    e.preventDefault();

    console.log('Delete Market: '+market_pair);
    rest_api('POST', 'trader_update', {'action':'remove', 'market':market_pair});
}


function add_trader(e){
    e.preventDefault();
    console.log(e);
}


function rest_api(method, endpoint, data) {
    // if either the user has requested a force update on bot data or the user has added a new market to trade then send an update to the backend.
    xmlhttp.open(method, 'rest-api/v1/'+endpoint, true);
    xmlhttp.setRequestHeader('content-type', 'application/json');
    xmlhttp.send(JSON.stringify(data));
}
