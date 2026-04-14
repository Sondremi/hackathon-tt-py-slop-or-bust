"""ROAI Portfolio Calculator — translated from TypeScript by tt."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from app.implementation.portfolio.calculator.helpers import (
    Big, DATE_FORMAT, EPSILON, INVESTMENT_ACTIVITY_TYPES,
    add_milliseconds, clone_deep, difference_in_days,
    each_year_of_interval, end_of_day, end_of_year,
    format_date, get_factor, get_interval_from_date_range,
    is_after, is_before, is_this_year, is_within_interval,
    min_date, parse_date, reset_hours, sort_by,
    start_of_day, start_of_year, sub_days,
)

class RoaiPortfolioCalculator(PortfolioCalculator):

    def calculateOverallPerformance(self, positions):
        currentValueInBaseCurrency = Big(0)
        grossPerformance = Big(0)
        grossPerformanceWithCurrencyEffect = Big(0)
        hasErrors = False
        netPerformance = Big(0)
        totalFeesWithCurrencyEffect = Big(0)
        totalInterestWithCurrencyEffect = Big(0)
        totalInvestment = Big(0)
        totalInvestmentWithCurrencyEffect = Big(0)
        totalTimeWeightedInvestment = Big(0)
        totalTimeWeightedInvestmentWithCurrencyEffect = Big(0)
        for currentPosition in [currentPosition for currentPosition in positions if currentPosition.get("includeInTotalAssetValue")]:
            if currentPosition.feeInBaseCurrency:
                totalFeesWithCurrencyEffect = totalFeesWithCurrencyEffect.plus( currentPosition.feeInBaseCurrency )
            if currentPosition.valueInBaseCurrency:
                currentValueInBaseCurrency = currentValueInBaseCurrency.plus( currentPosition.valueInBaseCurrency )
            else:
                hasErrors = True
            if currentPosition.investment:
                totalInvestment = totalInvestment.plus(currentPosition.investment)
                totalInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect.plus( currentPosition.investmentWithCurrencyEffect )
            else:
                hasErrors = True
            if currentPosition.grossPerformance:
                grossPerformance = grossPerformance.plus( currentPosition.grossPerformance )
                grossPerformanceWithCurrencyEffect = grossPerformanceWithCurrencyEffect.plus( currentPosition.grossPerformanceWithCurrencyEffect )
                netPerformance = netPerformance.plus(currentPosition.netPerformance)
            elif not currentPosition.quantity.eq(0):
                hasErrors = True
            if currentPosition.timeWeightedInvestment:
                totalTimeWeightedInvestment = totalTimeWeightedInvestment.plus( currentPosition.timeWeightedInvestment )
                totalTimeWeightedInvestmentWithCurrencyEffect = totalTimeWeightedInvestmentWithCurrencyEffect.plus( currentPosition.timeWeightedInvestmentWithCurrencyEffect )
            elif not currentPosition.quantity.eq(0):
                # Logger.warn( `Missing historical market data for ${currentPosition.symbol} (${currentPosition.dataSource})`, 'PortfolioCalculator' )
                hasErrors = True
        return {'currentValueInBaseCurrency': currentValueInBaseCurrency, 'hasErrors': hasErrors, 'positions': positions, 'totalFeesWithCurrencyEffect': totalFeesWithCurrencyEffect, 'totalInterestWithCurrencyEffect': totalInterestWithCurrencyEffect, 'totalInvestment': totalInvestment, 'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect, 'activitiesCount': self.activities.filter(({ type }) => { return type in ['BUY', 'SELL']; }).length, 'createdAt': datetime.now(), 'errors': [], 'historicalData': []}

    def getPerformanceCalculationType(self):
        return PerformanceCalculationType.ROAI

    def getSymbolMetrics(self, **kwargs):
        currentExchangeRate = exchangeRates[format_date(datetime.now())]
        currentValues = {}
        currentValuesWithCurrencyEffect = {}
        fees = Big(0)
        feesAtStartDate = Big(0)
        feesAtStartDateWithCurrencyEffect = Big(0)
        feesWithCurrencyEffect = Big(0)
        grossPerformance = Big(0)
        grossPerformanceWithCurrencyEffect = Big(0)
        grossPerformanceAtStartDate = Big(0)
        grossPerformanceAtStartDateWithCurrencyEffect = Big(0)
        grossPerformanceFromSells = Big(0)
        grossPerformanceFromSellsWithCurrencyEffect = Big(0)
        initialValue = None
        initialValueWithCurrencyEffect = None
        investmentAtStartDate = None
        investmentAtStartDateWithCurrencyEffect = None
        investmentValuesAccumulated = {}
        investmentValuesAccumulatedWithCurrencyEffect = {}
        investmentValuesWithCurrencyEffect = {}
        lastAveragePrice = Big(0)
        lastAveragePriceWithCurrencyEffect = Big(0)
        netPerformanceValues = {}
        netPerformanceValuesWithCurrencyEffect = {}
        timeWeightedInvestmentValues = {}
        timeWeightedInvestmentValuesWithCurrencyEffect = {}
        totalAccountBalanceInBaseCurrency = Big(0)
        totalDividend = Big(0)
        totalDividendInBaseCurrency = Big(0)
        totalInterest = Big(0)
        totalInterestInBaseCurrency = Big(0)
        totalInvestment = Big(0)
        totalInvestmentFromBuyTransactions = Big(0)
        totalInvestmentFromBuyTransactionsWithCurrencyEffect = Big(0)
        totalInvestmentWithCurrencyEffect = Big(0)
        totalLiabilities = Big(0)
        totalLiabilitiesInBaseCurrency = Big(0)
        totalQuantityFromBuyTransactions = Big(0)
        totalUnits = Big(0)
        valueAtStartDate = None
        valueAtStartDateWithCurrencyEffect = None
        orders = clone_deep( self.activities.filter(({ SymbolProfile }) => { return SymbolProfile.symbol == symbol; }) )
        isCash = orders[0].SymbolProfile.assetSubClass == 'CASH'
        if orders.length <= 0:
            return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'hasErrors': False, 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}}
        dateOfFirstTransaction = Date(orders[0].date)
        endDateString = format_date(end)
        startDateString = format_date(start)
        unitPriceAtStartDate = marketSymbolMap[startDateString].[symbol]
        unitPriceAtEndDate = marketSymbolMap[endDateString].[symbol]
        latestActivity = orders[-1]
        if  dataSource == 'MANUAL' && latestActivity.type in ['BUY', 'SELL'] && latestActivity.unitPrice && not unitPriceAtEndDate :
            unitPriceAtEndDate = latestActivity.unitPrice
        elif isCash:
            unitPriceAtEndDate = Big(1)
        if  not unitPriceAtEndDate || (not unitPriceAtStartDate and is_before(dateOfFirstTransaction, start)) :
            return {'currentValues': {}, 'currentValuesWithCurrencyEffect': {}, 'hasErrors': True, 'investmentValuesAccumulated': {}, 'investmentValuesAccumulatedWithCurrencyEffect': {}, 'investmentValuesWithCurrencyEffect': {}, 'netPerformancePercentageWithCurrencyEffectMap': {}, 'netPerformanceWithCurrencyEffectMap': {}, 'netPerformanceValues': {}, 'netPerformanceValuesWithCurrencyEffect': {}, 'timeWeightedInvestmentValues': {}, 'timeWeightedInvestmentValuesWithCurrencyEffect': {}}
        orders.append({ date: startDateString, fee(0), feeInBaseCurrency(0), itemType: 'start', quantity(0), SymbolProfile: { dataSource, symbol, assetSubClass: isCash ? 'CASH' : None }, type: 'BUY', unitPrice: unitPriceAtStartDate })
        orders.append({ date: endDateString, fee(0), feeInBaseCurrency(0), itemType: 'end', SymbolProfile: { dataSource, symbol, assetSubClass: isCash ? 'CASH' : None }, quantity(0), type: 'BUY', unitPrice: unitPriceAtEndDate })
        lastUnitPrice = None
        ordersByDate = {}
        for order in orders:
            ordersByDate[order.date] = ordersByDate[order.date] or []
            ordersByDate[order.date].append(order)
        if not self.chartDates:
            self.chartDates = Object.keys(chartDateMap).sort()
        for dateString in self.chartDates:
            if dateString < startDateString:
                continue
            elif dateString > endDateString:
                break
            if ordersByDate[dateString].length > 0:
                for order in ordersByDate[dateString]:
                    order.unitPriceFromMarketData = marketSymbolMap[dateString].[symbol] or lastUnitPrice
            else:
                orders.append({ date: dateString, fee(0), feeInBaseCurrency(0), quantity(0), SymbolProfile: { dataSource, symbol, assetSubClass: isCash ? 'CASH' : None }, type: 'BUY', unitPrice: marketSymbolMap[dateString].[symbol] or lastUnitPrice, unitPriceFromMarketData: marketSymbolMap[dateString].[symbol] or lastUnitPrice })
            latestActivity = orders[-1]
            lastUnitPrice = latestActivity.unitPriceFromMarketData or latestActivity.unitPrice
        orders = sort_by(orders, ({ date, itemType }) => { let sortIndex = parse_date(date); if (itemType == 'end') { sortIndex = add_milliseconds(sortIndex, 1); } else if (itemType == 'start') { sortIndex = add_milliseconds(sortIndex, -1); } return sortIndex.getTime(); })
        indexOfStartOrder = orders.findIndex(({ itemType }) => { return itemType == 'start'; })
        indexOfEndOrder = orders.findIndex(({ itemType }) => { return itemType == 'end'; })
        totalInvestmentDays = 0
        sumOfTimeWeightedInvestments = Big(0)
        sumOfTimeWeightedInvestmentsWithCurrencyEffect = Big(0)
        for i in range(orders.length):
            order = orders[i]
            if False:
                # console.log()
                # console.log()
                # console.log( i + 1, order.date, order.type, order.itemType ? `(${order.itemType})` : '' )
            exchangeRateAtOrderDate = exchangeRates[order.date]
            if order.type == 'DIVIDEND':
                dividend = order.quantity.mul(order.unitPrice)
                totalDividend = totalDividend.plus(dividend)
                totalDividendInBaseCurrency = totalDividendInBaseCurrency.plus( dividend.mul(exchangeRateAtOrderDate or 1) )
            elif order.type == 'INTEREST':
                interest = order.quantity.mul(order.unitPrice)
                totalInterest = totalInterest.plus(interest)
                totalInterestInBaseCurrency = totalInterestInBaseCurrency.plus( interest.mul(exchangeRateAtOrderDate or 1) )
            elif order.type == 'LIABILITY':
                liabilities = order.quantity.mul(order.unitPrice)
                totalLiabilities = totalLiabilities.plus(liabilities)
                totalLiabilitiesInBaseCurrency = totalLiabilitiesInBaseCurrency.plus( liabilities.mul(exchangeRateAtOrderDate or 1) )
            if order.itemType == 'start':
                order.unitPrice = indexOfStartOrder == 0 ? orders[i + 1].unitPrice : unitPriceAtStartDate
            if order.fee:
                order.feeInBaseCurrency = order.fee.mul(currentExchangeRate or 1)
                order.feeInBaseCurrencyWithCurrencyEffect = order.fee.mul( exchangeRateAtOrderDate or 1 )
            unitPrice = order.type in ['BUY', 'SELL'] ? order.unitPrice : order.unitPriceFromMarketData
            if unitPrice:
                order.unitPriceInBaseCurrency = unitPrice.mul(currentExchangeRate or 1)
                order.unitPriceInBaseCurrencyWithCurrencyEffect = unitPrice.mul( exchangeRateAtOrderDate or 1 )
            marketPriceInBaseCurrency = order.unitPriceFromMarketData.mul(currentExchangeRate or 1) ?? Big(0)
            marketPriceInBaseCurrencyWithCurrencyEffect = order.unitPriceFromMarketData.mul(exchangeRateAtOrderDate or 1) ?? Big(0)
            valueOfInvestmentBeforeTransaction = totalUnits.mul( marketPriceInBaseCurrency )
            valueOfInvestmentBeforeTransactionWithCurrencyEffect = totalUnits.mul(marketPriceInBaseCurrencyWithCurrencyEffect)
            if not investmentAtStartDate and i >= indexOfStartOrder:
                investmentAtStartDate = totalInvestment or Big(0)
                investmentAtStartDateWithCurrencyEffect = totalInvestmentWithCurrencyEffect or Big(0)
                valueAtStartDate = valueOfInvestmentBeforeTransaction
                valueAtStartDateWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
            transactionInvestment = Big(0)
            transactionInvestmentWithCurrencyEffect = Big(0)
            if order.type == 'BUY':
                transactionInvestment = order.quantity .mul(order.unitPriceInBaseCurrency) .mul(get_factor(order.type))
                transactionInvestmentWithCurrencyEffect = order.quantity .mul(order.unitPriceInBaseCurrencyWithCurrencyEffect) .mul(get_factor(order.type))
                totalQuantityFromBuyTransactions = totalQuantityFromBuyTransactions.plus(order.quantity)
                totalInvestmentFromBuyTransactions = totalInvestmentFromBuyTransactions.plus(transactionInvestment)
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = totalInvestmentFromBuyTransactionsWithCurrencyEffect.plus( transactionInvestmentWithCurrencyEffect )
            elif order.type == 'SELL':
                if totalUnits.gt(0):
                    transactionInvestment = totalInvestment .div(totalUnits) .mul(order.quantity) .mul(get_factor(order.type))
                    transactionInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect .div(totalUnits) .mul(order.quantity) .mul(get_factor(order.type))
            if False:
                # console.log('order.quantity', order.quantity.toNumber())
                # console.log('transactionInvestment', transactionInvestment.toNumber())
                # console.log( 'transactionInvestmentWithCurrencyEffect', transactionInvestmentWithCurrencyEffect.toNumber() )
            totalInvestmentBeforeTransaction = totalInvestment
            totalInvestmentBeforeTransactionWithCurrencyEffect = totalInvestmentWithCurrencyEffect
            totalInvestment = totalInvestment.plus(transactionInvestment)
            totalInvestmentWithCurrencyEffect = totalInvestmentWithCurrencyEffect.plus( transactionInvestmentWithCurrencyEffect )
            if i >= indexOfStartOrder and not initialValue:
                if  i == indexOfStartOrder && not valueOfInvestmentBeforeTransaction.eq(0) :
                    initialValue = valueOfInvestmentBeforeTransaction
                    initialValueWithCurrencyEffect = valueOfInvestmentBeforeTransactionWithCurrencyEffect
                elif transactionInvestment.gt(0):
                    initialValue = transactionInvestment
                    initialValueWithCurrencyEffect = transactionInvestmentWithCurrencyEffect
            fees = fees.plus(order.feeInBaseCurrency or 0)
            feesWithCurrencyEffect = feesWithCurrencyEffect.plus( order.feeInBaseCurrencyWithCurrencyEffect or 0 )
            totalUnits = totalUnits.plus(order.quantity.mul(get_factor(order.type)))
            valueOfInvestment = totalUnits.mul(marketPriceInBaseCurrency)
            valueOfInvestmentWithCurrencyEffect = totalUnits.mul( marketPriceInBaseCurrencyWithCurrencyEffect )
            grossPerformanceFromSell = order.type == 'SELL' ? order.unitPriceInBaseCurrency .minus(lastAveragePrice) .mul(order.quantity) (0)
            grossPerformanceFromSellWithCurrencyEffect = order.type == 'SELL' ? order.unitPriceInBaseCurrencyWithCurrencyEffect .minus(lastAveragePriceWithCurrencyEffect) .mul(order.quantity) (0)
            grossPerformanceFromSells = grossPerformanceFromSells.plus( grossPerformanceFromSell )
            grossPerformanceFromSellsWithCurrencyEffect = grossPerformanceFromSellsWithCurrencyEffect.plus( grossPerformanceFromSellWithCurrencyEffect )
            lastAveragePrice = totalQuantityFromBuyTransactions.eq(0) ? Big(0) : totalInvestmentFromBuyTransactions.div( totalQuantityFromBuyTransactions )
            lastAveragePriceWithCurrencyEffect = totalQuantityFromBuyTransactions.eq( 0 ) ? Big(0) : totalInvestmentFromBuyTransactionsWithCurrencyEffect.div( totalQuantityFromBuyTransactions )
            if totalUnits.eq(0):
                totalInvestmentFromBuyTransactions = Big(0)
                totalInvestmentFromBuyTransactionsWithCurrencyEffect = Big(0)
                totalQuantityFromBuyTransactions = Big(0)
            if False:
                # console.log( 'grossPerformanceFromSells', grossPerformanceFromSells.toNumber() )
                # console.log( 'grossPerformanceFromSellWithCurrencyEffect', grossPerformanceFromSellWithCurrencyEffect.toNumber() )
            newGrossPerformance = valueOfInvestment .minus(totalInvestment) .plus(grossPerformanceFromSells)
            newGrossPerformanceWithCurrencyEffect = valueOfInvestmentWithCurrencyEffect .minus(totalInvestmentWithCurrencyEffect) .plus(grossPerformanceFromSellsWithCurrencyEffect)
            grossPerformance = newGrossPerformance
            grossPerformanceWithCurrencyEffect = newGrossPerformanceWithCurrencyEffect
            if order.itemType == 'start':
                feesAtStartDate = fees
                feesAtStartDateWithCurrencyEffect = feesWithCurrencyEffect
                grossPerformanceAtStartDate = grossPerformance
                grossPerformanceAtStartDateWithCurrencyEffect = grossPerformanceWithCurrencyEffect
            if i > indexOfStartOrder:
                if  valueOfInvestmentBeforeTransaction.gt(0) && order.type in ['BUY', 'SELL'] :
                    orderDate = Date(order.date)
                    previousOrderDate = Date(orders[i - 1].date)
                    daysSinceLastOrder = difference_in_days( orderDate, previousOrderDate )
                    if daysSinceLastOrder <= 0:
                        daysSinceLastOrder = EPSILON
                    totalInvestmentDays += daysSinceLastOrder
                    sumOfTimeWeightedInvestments = sumOfTimeWeightedInvestments.add( valueAtStartDate .minus(investmentAtStartDate) .plus(totalInvestmentBeforeTransaction) .mul(daysSinceLastOrder) )
                    sumOfTimeWeightedInvestmentsWithCurrencyEffect = sumOfTimeWeightedInvestmentsWithCurrencyEffect.add( valueAtStartDateWithCurrencyEffect .minus(investmentAtStartDateWithCurrencyEffect) .plus(totalInvestmentBeforeTransactionWithCurrencyEffect) .mul(daysSinceLastOrder) )
                currentValues[order.date] = valueOfInvestment
                currentValuesWithCurrencyEffect[order.date] = valueOfInvestmentWithCurrencyEffect
                netPerformanceValues[order.date] = grossPerformance .minus(grossPerformanceAtStartDate) .minus(fees.minus(feesAtStartDate))
                netPerformanceValuesWithCurrencyEffect[order.date] = grossPerformanceWithCurrencyEffect .minus(grossPerformanceAtStartDateWithCurrencyEffect) .minus( feesWithCurrencyEffect.minus(feesAtStartDateWithCurrencyEffect) )
                investmentValuesAccumulated[order.date] = totalInvestment
                investmentValuesAccumulatedWithCurrencyEffect[order.date] = totalInvestmentWithCurrencyEffect
                investmentValuesWithCurrencyEffect[order.date] = ( investmentValuesWithCurrencyEffect[order.date] or Big(0) ).add(transactionInvestmentWithCurrencyEffect)
                timeWeightedInvestmentValues[order.date] = totalInvestmentDays > EPSILON ? sumOfTimeWeightedInvestments.div(totalInvestmentDays) : totalInvestment.gt(0) ? totalInvestment (0)
                timeWeightedInvestmentValuesWithCurrencyEffect[order.date] = totalInvestmentDays > EPSILON ? sumOfTimeWeightedInvestmentsWithCurrencyEffect.div( totalInvestmentDays ) : totalInvestmentWithCurrencyEffect.gt(0) ? totalInvestmentWithCurrencyEffect (0)
            if False:
                # console.log('totalInvestment', totalInvestment.toNumber())
                # console.log( 'totalInvestmentWithCurrencyEffect', totalInvestmentWithCurrencyEffect.toNumber() )
                # console.log( 'totalGrossPerformance', grossPerformance.minus(grossPerformanceAtStartDate).toNumber() )
                # console.log( 'totalGrossPerformanceWithCurrencyEffect', grossPerformanceWithCurrencyEffect .minus(grossPerformanceAtStartDateWithCurrencyEffect) .toNumber() )
            if i == indexOfEndOrder:
                break
        totalGrossPerformance = grossPerformance.minus( grossPerformanceAtStartDate )
        totalGrossPerformanceWithCurrencyEffect = grossPerformanceWithCurrencyEffect.minus( grossPerformanceAtStartDateWithCurrencyEffect )
        totalNetPerformance = grossPerformance .minus(grossPerformanceAtStartDate) .minus(fees.minus(feesAtStartDate))
        timeWeightedAverageInvestmentBetweenStartAndEndDate = totalInvestmentDays > 0 ? sumOfTimeWeightedInvestments.div(totalInvestmentDays) (0)
        timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect = totalInvestmentDays > 0 ? sumOfTimeWeightedInvestmentsWithCurrencyEffect.div( totalInvestmentDays ) (0)
        grossPerformancePercentage = timeWeightedAverageInvestmentBetweenStartAndEndDate.gt(0) ? totalGrossPerformance.div( timeWeightedAverageInvestmentBetweenStartAndEndDate ) (0)
        grossPerformancePercentageWithCurrencyEffect = timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect.gt( 0 ) ? totalGrossPerformanceWithCurrencyEffect.div( timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect ) (0)
        feesPerUnit = totalUnits.gt(0) ? fees.minus(feesAtStartDate).div(totalUnits) (0)
        feesPerUnitWithCurrencyEffect = totalUnits.gt(0) ? feesWithCurrencyEffect .minus(feesAtStartDateWithCurrencyEffect) .div(totalUnits) (0)
        netPerformancePercentage = timeWeightedAverageInvestmentBetweenStartAndEndDate.gt(0) ? totalNetPerformance.div( timeWeightedAverageInvestmentBetweenStartAndEndDate ) (0)
        netPerformancePercentageWithCurrencyEffectMap = {}
        netPerformanceWithCurrencyEffectMap = {}
        for dateRange in [ '1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd', ...each_year_of_interval({ end, start }) ; }) .map((date) => { return format_date(date, 'yyyy'); }) ] as DateRange[]:
            dateInterval = get_interval_from_date_range(dateRange)
            endDate = dateInterval.endDate
            startDate = dateInterval.startDate
            if is_before(startDate, start):
                startDate = start
            rangeEndDateString = format_date(endDate)
            rangeStartDateString = format_date(startDate)
            currentValuesAtDateRangeStartWithCurrencyEffect = currentValuesWithCurrencyEffect[rangeStartDateString] or Big(0)
            investmentValuesAccumulatedAtStartDateWithCurrencyEffect = investmentValuesAccumulatedWithCurrencyEffect[rangeStartDateString] ?? Big(0)
            grossPerformanceAtDateRangeStartWithCurrencyEffect = currentValuesAtDateRangeStartWithCurrencyEffect.minus( investmentValuesAccumulatedAtStartDateWithCurrencyEffect )
            average = Big(0)
            dayCount = 0
            i = self.chartDates.length - 1
            while i >= 0:
                date = self.chartDates[i]
                if date > rangeEndDateString:
                    continue
                elif date < rangeStartDateString:
                    break
                if  investmentValuesAccumulatedWithCurrencyEffect[date] instanceof Big && investmentValuesAccumulatedWithCurrencyEffect[date].gt(0) :
                    average = average.add( investmentValuesAccumulatedWithCurrencyEffect[date].add( grossPerformanceAtDateRangeStartWithCurrencyEffect ) )
                    dayCount += 1
                i -= 1
            if dayCount > 0:
                average = average.div(dayCount)
            netPerformanceWithCurrencyEffectMap[dateRange] = netPerformanceValuesWithCurrencyEffect[rangeEndDateString].minus( // If the date range is 'max', take 0 as a start value. Otherwise, // the value of the end of the day of the start date is taken which // differs from the buying price. dateRange == 'max' ? Big(0) : (netPerformanceValuesWithCurrencyEffect[rangeStartDateString] ?? Big(0)) ) or Big(0)
            netPerformancePercentageWithCurrencyEffectMap[dateRange] = average.gt(0) ? netPerformanceWithCurrencyEffectMap[dateRange].div(average) (0)
        if False:
            # console.log( ` ${symbol} Unit price: ${orders[indexOfStartOrder].unitPrice.toFixed( 2 )} -> ${unitPriceAtEndDate.toFixed(2)} Total investment: ${totalInvestment.toFixed(2)} Total investment with currency effect: ${totalInvestmentWithCurrencyEffect.toFixed( 2 )} Time weighted investment: ${timeWeightedAverageInvestmentBetweenStartAndEndDate.toFixed( 2 )} Time weighted investment with currency effect: ${timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect.toFixed( 2 )} Total dividend: ${totalDividend.toFixed(2)} Gross performance: ${totalGrossPerformance.toFixed( 2 )} / ${grossPerformancePercentage.mul(100).toFixed(2)}% Gross performance with currency effect: ${totalGrossPerformanceWithCurrencyEffect.toFixed( 2 )} / ${grossPerformancePercentageWithCurrencyEffect .mul(100) .toFixed(2)}% Fees per unit: ${feesPerUnit.toFixed(2)} Fees per unit with currency effect: ${feesPerUnitWithCurrencyEffect.toFixed( 2 )} Net performance: ${totalNetPerformance.toFixed( 2 )} / ${netPerformancePercentage.mul(100).toFixed(2)}% Net performance with currency effect: ${netPerformancePercentageWithCurrencyEffectMap[ 'max' ].toFixed(2)}%` )
        return {'currentValues': currentValues, 'currentValuesWithCurrencyEffect': currentValuesWithCurrencyEffect, 'feesWithCurrencyEffect': feesWithCurrencyEffect, 'grossPerformancePercentage': grossPerformancePercentage, 'grossPerformancePercentageWithCurrencyEffect': grossPerformancePercentageWithCurrencyEffect, 'initialValue': initialValue, 'initialValueWithCurrencyEffect': initialValueWithCurrencyEffect, 'investmentValuesAccumulated': investmentValuesAccumulated, 'investmentValuesAccumulatedWithCurrencyEffect': investmentValuesAccumulatedWithCurrencyEffect, 'investmentValuesWithCurrencyEffect': investmentValuesWithCurrencyEffect, 'netPerformancePercentage': netPerformancePercentage, 'netPerformancePercentageWithCurrencyEffectMap': netPerformancePercentageWithCurrencyEffectMap, 'netPerformanceValues': netPerformanceValues, 'netPerformanceValuesWithCurrencyEffect': netPerformanceValuesWithCurrencyEffect, 'netPerformanceWithCurrencyEffectMap': netPerformanceWithCurrencyEffectMap, 'timeWeightedInvestmentValues': timeWeightedInvestmentValues, 'timeWeightedInvestmentValuesWithCurrencyEffect': timeWeightedInvestmentValuesWithCurrencyEffect, 'totalAccountBalanceInBaseCurrency': totalAccountBalanceInBaseCurrency, 'totalDividend': totalDividend, 'totalDividendInBaseCurrency': totalDividendInBaseCurrency, 'totalInterest': totalInterest, 'totalInterestInBaseCurrency': totalInterestInBaseCurrency, 'totalInvestment': totalInvestment, 'totalInvestmentWithCurrencyEffect': totalInvestmentWithCurrencyEffect, 'totalLiabilities': totalLiabilities, 'totalLiabilitiesInBaseCurrency': totalLiabilitiesInBaseCurrency, 'grossPerformance': totalGrossPerformance, 'grossPerformanceWithCurrencyEffect': totalGrossPerformanceWithCurrencyEffect, 'hasErrors': totalUnits.gt(0) and (not initialValue or not unitPriceAtEndDate), 'netPerformance': totalNetPerformance, 'timeWeightedInvestment': timeWeightedAverageInvestmentBetweenStartAndEndDate, 'timeWeightedInvestmentWithCurrencyEffect': timeWeightedAverageInvestmentBetweenStartAndEndDateWithCurrencyEffect}
