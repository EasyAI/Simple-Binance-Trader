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

    currentTraders = data['data'];
    console.log(currentTraders);

    for (i = 0; i < (currentTraders.length); i++){
        row = document.createElement('tr');
        row.setAttribute('id', 'trader-section');

        current = currentTraders[i];

        market_pair = current['market'];

        market_activity = current['market_activity'];

        trade_recorder = current['trade_recorder'];

        total_price_string  = `${market_activity['order_market_type']} ${market_activity['order_side']} | Type:${market_activity['order_type']} | Status:${market_activity['order_status']} `;

        if (market_activity['order_side'] == 'SELL') {
            total_price_string  += `| Buy Price:${trade_recorder[trade_recorder.length-1][1]} | Sell Price:${market_activity['price']}`;
        } else {
            total_price_string += `| Buy Price:${market_activity['price']}`
        }

        buttonStart     = `<a href=# class="small-button green-button" onclick="start_trader(event, '${market_pair}');">Start</a>`;
        buttonPause     = `<a href=# class="small-button amber-button" onclick="pause_trader(event, '${market_pair}');">Pause</a>`;
        buttonRemove    = `<a href=# class="small-button red-button" onclick="delete_trader(event, '${market_pair}');">Remove</a>`;

        // 

        var outcome = 0;
        var total_trades = 0;

        if (trade_recorder.length >= 2) {
            range = trade_recorder.length/2
            for (i = 0; i < (range); i++) {
                buy_order = trade_recorder[(range*2)-2]
                sell_order = trade_recorder[range*2-1]

                buy_value = buy_order[1]*buy_order[2]
                sell_value = sell_order[1]*buy_order[2]

                outcome = sell_value-buy_value
                total_trades += 1
            }
        }

        row.innerHTML   = `
            <td id="market-pair">${market_pair}</td>
            <td id="main-data">State: ${current['state_data']['runtime_state']} | Trades: ${total_trades} | Overall: ${Math.round(outcome*100000000)/100000000} | Last Update: ${current['state_data']['last_update_time']} | Last Price: ${current['market_prices']['lastPrice']}<br>
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