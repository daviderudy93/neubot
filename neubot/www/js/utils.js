/* neubot/www/utils.js */
/*
 * Copyright (c) 2011 Alessio Palmero Aprosio <alessio@apnetwork.it>,
 *  Università degli Studi di Milano
 * Copyright (c) 2010 Simone Basso <bassosimone@gmail.com>,
 *  NEXA Center for Internet & Society at Politecnico di Torino
 *
 * This file is part of Neubot <http://www.neubot.org/>.
 *
 * Neubot is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Neubot is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Neubot.  If not, see <http://www.gnu.org/licenses/>.
 */

var utils = (function() {
    var self = {};

    self.toMs = function(x) {
        return (1000 * x).toFixed(0) + " ms";
    }
    self.toMbitsPerSecondNumber = function(x) {
        return (x * 8 / 1000 / 1000).toFixed(3);
    }
    self.toMbitsPerSecond = function(x) {
        return (x * 8 / 1000 / 1000).toFixed(3) + " Mbit/s";
    }
    self.getText = function(text) {
        if (text == "")
            return (text);
        text = jQuery.trim(text);
        return (text);
    }
    self.getNumber = function(text) {
        if (text == "") {
            return (text);
        }
        var number = Number(text);
        return (number);
    }
    self.getNow = function() {
        var date = new Date();
        return date.getTime();
    }
    self.getTimeFromMicroseconds = function(t, convert) {
        t = self.getNumber(t);
        if (!t) {
            t = utils.getNow();
        }
        else {
            t = t / 1000;
        }
        if (convert) {
            t = formatTime(t);
        }
        return t;
    }
    self.getTimeFromSeconds = function(t, convert) {
        t = self.getNumber(t);
        if (!t) {
            t = utils.getNow();
        }
        else {
            t *= 1000;
        }
        if (convert) {
            t = utils.formatDateTime(t);
        }
        return t;
    }
    self.formatMinutes = function(t) {
        t = t / 1000;
        tm = Math.ceil(t / 60);

        // Change t to tm to differentiate from timestamp
        if (tm > 1) {
            s = tm + " minutes";
        }
        else {
            s = "Less than one minute";
        }
        return (s);
    }
    self.strPad = function(n) {
        return n < 10 ? '0' + n : n
    }
    self.formatDateTime = function(t) {
        var date = new Date(t);
        return date.getFullYear() + '-' + self.strPad(date.getMonth() + 1)
          + '-' + self.strPad(date.getDate()) + '\n' + self.strPad(date.getHours()) + ':'
          + self.strPad(date.getMinutes());
    }

    return self;
})();
