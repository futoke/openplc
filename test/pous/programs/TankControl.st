PROGRAM TankControl
  VAR
    StartBtn : BOOL AT %MX0.0 := False;
    StopBtn : BOOL AT %MX0.1 := False;
    ResetBtn : BOOL AT %MX0.2 := False;
    LowLevel : BOOL AT %MX0.3 := False;
    HighLevel : BOOL AT %MX0.4 := False;
    Pump : BOOL AT %QX1.0 := False;
    Alarm : BOOL AT %QX1.1 := False;
    AutoMode : BOOL AT %QX1.2 := False;
    FillTimer : TON;
  END_VAR
  VAR_INPUT
  END_VAR

(* ====================================== *)
(* TankControl - управление резервуаром    *)
(* ====================================== *)

(* Сброс аварии *)
IF ResetBtn THEN
    IF NOT (HighLevel AND NOT LowLevel) THEN
        Alarm := FALSE;
        AutoMode := FALSE;
    END_IF;
END_IF;

(* Запуск и остановка *)
IF StopBtn THEN
    AutoMode := FALSE;
ELSIF StartBtn AND NOT Alarm THEN
    AutoMode := TRUE;
END_IF;

(* Контроль неисправности датчиков *)
IF HighLevel AND NOT LowLevel THEN
    Alarm := TRUE;
    AutoMode := FALSE;
END_IF;

(* Управление насосом с гистерезисом *)
IF NOT AutoMode OR Alarm THEN
    Pump := FALSE;

ELSIF HighLevel THEN
    (* Верхний уровень достигнут *)
    Pump := FALSE;

ELSIF NOT LowLevel THEN
    (* Уровень ниже нижнего датчика *)
    Pump := TRUE;
END_IF;

(* Таймер максимального наполнения *)
FillTimer(
    IN := Pump,
    PT := T#30s
);

(* Авария, если насос слишком долго *)
(* работает без достижения верхнего уровня *)
IF FillTimer.Q THEN
    Alarm := TRUE;
    AutoMode := FALSE;
    Pump := FALSE;
END_IF;

END_PROGRAM