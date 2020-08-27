//
var socket = io('http://127.0.0.1:5000');
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

        market_pair      = current['symbol'];
        overall          = current['tradeInfo']['overall'];

        if (current['tradeInfo']['orderType']['S'] == null){
            PriceString  = `BUY | Type:${current['tradeInfo']['orderType']['B']} | Status:${current['tradeInfo']['orderStatus']['B']} | Buy Price:${current['tradeInfo']['buyPrice']} | Last Price: ${current['prices']['lastPrice']}`;
        } else {
            PriceString  = `SELL | Type:${current['tradeInfo']['orderType']['S']} | Status:${current['tradeInfo']['orderStatus']['S']} | Buy Price:${current['tradeInfo']['buyPrice']} | Sell Price:${current['tradeInfo']['sellPrice']} | Last Price: ${current['prices']['lastPrice']}`;
        }
     
        buttonStart     = `<a href=# class="small-button green-button" onclick="start_trader(event, '${market_pair}');">Start</a>`;
        buttonPause     = `<a href=# class="small-button amber-button" onclick="pause_trader(event, '${market_pair}');">Pause</a>`;
        buttonRemove    = `<a href=# class="small-button red-button" onclick="delete_trader(event, '${market_pair}');">Remove</a>`;

        row.innerHTML   = `
            <td id="market-pair">${market_pair}</td>
            <td id="main-data">State: ${current['state']} | Trades: ${current['tradeInfo']['#Trades']} | Overall: ${Math.round(current['tradeInfo']['overall']*100000000)/100000000} | Last Update: ${current['lastUpdate']}<br>
            ${PriceString}</td>
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
