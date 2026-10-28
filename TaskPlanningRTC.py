#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-

# <rtc-template block="description">
"""
 @file TaskPlanningRTC.py
 @brief ModuleDescription
 @date $Date$


"""
# </rtc-template>
import json
import math
import os
import sys
import time
sys.path.append(".")

# Import RTM module
import RTC
import OpenRTM_aist


# Import Service implementation class
# <rtc-template block="service_impl">

# </rtc-template>

# Import Service stub modules
# <rtc-template block="consumer_import">
# </rtc-template>


# This module's spesification
# <rtc-template block="module_spec">
taskplanningrtc_spec = ["implementation_id", "TaskPlanningRTC", 
         "type_name",         "TaskPlanningRTC", 
         "description",       "ModuleDescription", 
         "version",           "1.0.0", 
         "vendor",            "VenderName", 
         "category",          "Category", 
         "activity_type",     "STATIC", 
         "max_instance",      "1", 
         "language",          "Python", 
         "lang_type",         "SCRIPT",
         ""]
# </rtc-template>

# <rtc-template block="component_description">
##
# @class TaskPlanningRTC
# @brief ModuleDescription
# 
# 
# </rtc-template>
class TaskPlanningRTC(OpenRTM_aist.DataFlowComponentBase):
    
    ##
    # @brief constructor
    # @param manager Maneger Object
    # 
    def __init__(self, manager):
        OpenRTM_aist.DataFlowComponentBase.__init__(self, manager)

        self._d_TrgList = OpenRTM_aist.instantiateDataType(RTC.TimedLongSeq)
        """
        """
        self._TrgListIn = OpenRTM_aist.InPort("TrgList", self._d_TrgList)
        self._d_TaskRequest = OpenRTM_aist.instantiateDataType(RTC.TimedBoolean)
        """
        """
        self._TaskRequestIn = OpenRTM_aist.InPort("TaskRequest", self._d_TaskRequest)
        self._d_Task = OpenRTM_aist.instantiateDataType(RTC.TimedLongSeq)
        """
        """
        self._TaskOut = OpenRTM_aist.OutPort("Task", self._d_Task)
        self._d_TimeOver = OpenRTM_aist.instantiateDataType(RTC.TimedBoolean)
        """
        """
        self._TimeOverOut = OpenRTM_aist.OutPort("TimeOver", self._d_TimeOver)


        

        # initialize of configuration-data.
        # <rtc-template block="init_conf_param">
        
        # </rtc-template>


         
    ##
    #
    # The initialize action (on CREATED->ALIVE transition)
    # 
    # @return RTC::ReturnCode_t
    # 
    #
    def onInitialize(self):
        # Bind variables and configuration variable
        
        # Set InPort buffers
        self.addInPort("TrgList",self._TrgListIn)
        self.addInPort("TaskRequest",self._TaskRequestIn)
        
        # Set OutPort buffers
        self.addOutPort("Task",self._TaskOut)
        self.addOutPort("TimeOver",self._TimeOverOut)
        
        # Set service provider to Ports
        
        # Set service consumers to Ports
        
        # Set CORBA Service Ports
        
        return RTC.RTC_OK
    
    ###
    ## 
    ## The finalize action (on ALIVE->END transition)
    ## 
    ## @return RTC::ReturnCode_t
    #
    ## 
    #def onFinalize(self):
    #

    #    return RTC.RTC_OK
    
    ###
    ##
    ## The startup action when ExecutionContext startup
    ## 
    ## @param ec_id target ExecutionContext Id
    ## 
    ## @return RTC::ReturnCode_t
    ##
    ##
    #def onStartup(self, ec_id):
    #
    #    return RTC.RTC_OK
    
    ###
    ##
    ## The shutdown action when ExecutionContext stop
    ##
    ## @param ec_id target ExecutionContext Id
    ##
    ## @return RTC::ReturnCode_t
    ## 
    ##
    #def onShutdown(self, ec_id):
    #
    #    return RTC.RTC_OK
    
    ##
    #
    # The activated action (Active state entry action)
    #
    # @param ec_id target ExecutionContext Id
    # 
    # @return RTC::ReturnCode_t
    #
    #
    def onActivated(self, ec_id):
        # ========================================
        # 1. 今回の状態を初期化
        # ========================================

        self.state = "INACTIVE"

        # 例：
        # [[1, 1], [2, 2, 2, 3], [4, 5]]
        self.task_list = []

        # 次に送信するタスクのインデックス
        self.task_index = 0

        # 目標商品リストを受信してから計時を開始
        self.start_time = None

        self._d_Task.data = []
        self._d_TimeOver.data = False

        # ========================================
        # 2. 外部設定を読み込む
        # ========================================

        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "task_config.json"
        )

        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                raise ValueError("設定内容はJSONオブジェクトである必要があります")

            self.total_time = config["total_time_sec"]
            self.warning_time = config["time_over_remaining_sec"]
            self.shelf_order = config["shelf_order"]

            # ========================================
            # 3. 時間と棚順序を確認
            # ========================================

            for value in (self.total_time, self.warning_time):
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                ):
                    raise ValueError("時間パラメータは有限の数値である必要があります")

            if not 0 <= self.warning_time < self.total_time:
                raise ValueError(
                    "時間パラメータは次を満たす必要があります："
                    "0 <= 事前通知時間 < 総制限時間"
                )

            if (
                self.shelf_order != [1, 2, 3, 4]
                or any(
                    type(shelf_id) is not int
                    for shelf_id in self.shelf_order
                )
            ):
                raise ValueError(
                    "shelf_orderは[1, 2, 3, 4]である必要があります"
                )

            # ========================================
            # 4. 商品IDと棚IDの対応関係を作成
            # ========================================

            products = config["products"]

            if not isinstance(products, list) or not products:
                raise ValueError("productsは空でないリストである必要があります")

            self.product_shelf = {}

            for product in products:
                if not isinstance(product, dict):
                    raise ValueError("各商品の設定はJSONオブジェクトである必要があります")

                product_id = product["id"]
                shelf_id = product["shelf_id"]

                if (
                    type(product_id) is not int
                    or not 1 <= product_id <= 2147483647
                ):
                    raise ValueError(
                        "商品IDは正の32ビット符号付き整数である必要があります"
                    )

                if product_id in self.product_shelf:
                    raise ValueError(
                        "商品IDが重複定義されています：{}".format(product_id)
                    )

                if (
                    type(shelf_id) is not int
                    or shelf_id not in self.shelf_order
                ):
                    raise ValueError(
                        "商品{}の棚IDが正しくありません".format(product_id)
                    )

                self.product_shelf[product_id] = shelf_id

            # ========================================
            # 5. 入力ポートの古いデータをクリア
            # ========================================

            for port in (self._TrgListIn, self._TaskRequestIn):
                # 無限ループを避けるため、クリア回数に上限を設ける
                for _ in range(1024):
                    if not port.isNew():
                        break
                    port.read()

                if port.isNew():
                    raise RuntimeError(
                        "入力データが継続して到着しています。上流の送信を停止してからActivateしてください"
                    )

        except Exception as e:
            self.state = "ERROR"
            print("[TaskPlanningRTC] 起動に失敗：", e, flush=True)
            return RTC.RTC_ERROR

        self.state = "IDLE"

        print(
            "[TaskPlanningRTC] 設定の読み込みに成功",
            "\n商品と棚の対応関係：", self.product_shelf,
            "\n総制限時間：", self.total_time, "秒",
            "\n残り", self.warning_time, "秒でTimeOverを送信",
            flush=True
        )

        return RTC.RTC_OK
    
    ##
    #
    # The deactivated action (Active state exit action)
    #
    # @param ec_id target ExecutionContext Id
    #
    # @return RTC::ReturnCode_t
    #
    #
    def onDeactivated(self, ec_id):
    
        return RTC.RTC_OK
    
    ##
    #
    # The execution action that is invoked periodically
    #
    # @param ec_id target ExecutionContext Id
    #
    # @return RTC::ReturnCode_t
    #
    #
    def onExecute(self, ec_id):
        if self.state in ("INACTIVE", "ERROR"):
            return RTC.RTC_OK

        try:
            # ========================================
            # 1. 時間の事前警告閾値に達したか確認
            # ========================================

            if self.state == "RUNNING":
                elapsed_time = time.monotonic() - self.start_time

                if elapsed_time >= self.total_time - self.warning_time:
                    self.state = "TIME_OVER"

                    self._d_TimeOver.data = True
                    OpenRTM_aist.setTimestamp(self._d_TimeOver)

                    if not self._TimeOverOut.write():
                        raise RuntimeError("TimeOverの送信に失敗")

                    print(
                        "[TaskPlanningRTC] TimeOver=True、タスクの送信を停止",
                        flush=True
                    )

            # ========================================
            # 2. MPのタスク要求を読み込む
            # ========================================

            task_requested = False

            if self._TaskRequestIn.isNew():
                self._d_TaskRequest = self._TaskRequestIn.read()
                task_requested = self._d_TaskRequest.data is True

            # この周期でTaskを送信する必要があるか
            send_task = False

            # ========================================
            # 3. 新しい目標商品リストを受信
            # ========================================

            if self._TrgListIn.isNew():
                self._d_TrgList = self._TrgListIn.read()
                received_time = time.monotonic()

                target_ids = list(self._d_TrgList.data)

                if self.state == "IDLE":

                    # 新しいラウンドの開始時、既にある要求は新しいタスクを進めない
                    task_requested = False

                    for _ in range(1024):
                        if not self._TaskRequestIn.isNew():
                            break
                        self._TaskRequestIn.read()

                    # 先にリスト全体を検証し、未知IDを含む一部のタスクは受け付けない
                    invalid_ids = [
                        product_id
                        for product_id in target_ids
                        if (
                            type(product_id) is not int
                            or product_id not in self.product_shelf
                        )
                    ]

                    if invalid_ids:
                        print(
                            "[TaskPlanningRTC] 目標リストを拒否、"
                            "未知または不正な商品IDが含まれています：",
                            invalid_ids,
                            flush=True
                        )
                        return RTC.RTC_OK

                    # 棚ごとに分類
                    shelf_products = {
                        shelf_id: []
                        for shelf_id in self.shelf_order
                    }

                    for product_id in target_ids:
                        shelf_id = self.product_shelf[product_id]

                        # 重複した商品IDを保持し、同一商品が複数存在することを表す
                        shelf_products[shelf_id].append(product_id)

                    # 棚1→4の順でタスクを生成し、空の棚はスキップ
                    self.task_list = []

                    for shelf_id in self.shelf_order:
                        product_ids = shelf_products[shelf_id]

                        if product_ids:
                            task = [shelf_id] + sorted(product_ids)
                            self.task_list.append(task)

                    self.task_index = 0
                    self.start_time = received_time
                    self.state = "RUNNING"

                    # リストを受信した直後に最初のタスクを送信
                    send_task = True

                    print(
                        "[TaskPlanningRTC] 目標商品：", target_ids,
                        "\n生成されたタスク：", self.task_list,
                        flush=True
                    )

                else:
                    print(
                        "[TaskPlanningRTC] 現在の状態は",
                        self.state,
                        "です。新しいTrgListは無視されます",
                        flush=True
                    )

            # ========================================
            # 4. MPが現在の棚を完了した後、次のタスクを要求
            # ========================================

            if self.state == "RUNNING" and task_requested:
                send_task = True

            # ========================================
            # 5. 棚タスクまたは終了シグナルを送信
            # ========================================

            if self.state == "RUNNING" and send_task:

                # 送信前に再度確認し、時間超過がタスク配信より優先されることを保証
                elapsed_time = time.monotonic() - self.start_time

                if elapsed_time >= self.total_time - self.warning_time:
                    self.state = "TIME_OVER"

                    self._d_TimeOver.data = True
                    OpenRTM_aist.setTimestamp(self._d_TimeOver)

                    if not self._TimeOverOut.write():
                        raise RuntimeError("TimeOverの送信に失敗")

                    print(
                        "[TaskPlanningRTC] TimeOver=True、タスクの送信を停止",
                        flush=True
                    )

                    return RTC.RTC_OK

                if self.task_index < len(self.task_list):
                    # まだ送信していない棚タスクがある
                    self._d_Task.data = list(
                        self.task_list[self.task_index]
                    )
                else:
                    # 空リスト、または最後の棚が完了
                    self._d_Task.data = [0, 0]

                OpenRTM_aist.setTimestamp(self._d_Task)

                if not self._TaskOut.write():
                    raise RuntimeError("Taskの送信に失敗")

                print(
                    "[TaskPlanningRTC] Task ->",
                    self._d_Task.data,
                    flush=True
                )

                if self.task_index < len(self.task_list):
                    # 送信成功後にのみインデックスを進める
                    self.task_index += 1
                else:
                    # 正常終了、次の目標リストを待つ
                    self.state = "IDLE"
                    self.start_time = None
                    self.task_list = []
                    self.task_index = 0

        except Exception as e:
            self.state = "ERROR"
            print("[TaskPlanningRTC] 実行エラー：", e, flush=True)
            return RTC.RTC_ERROR
        return RTC.RTC_OK
    
    ###
    ##
    ## The aborting action when main logic error occurred.
    ##
    ## @param ec_id target ExecutionContext Id
    ##
    ## @return RTC::ReturnCode_t
    ##
    ##
    #def onAborting(self, ec_id):
    #
    #    return RTC.RTC_OK
    
    ###
    ## 
    ## The error action in ERROR state
    ##
    ## @param ec_id target ExecutionContext Id
    ##
    ## @return RTC::ReturnCode_t
    ##
    ##
    #def onError(self, ec_id):
    #
    #    return RTC.RTC_OK
    
    ###
    ## 
    ## The reset action that is invoked resetting
    ##
    ## @param ec_id target ExecutionContext Id
    ##
    ## @return RTC::ReturnCode_t
    ##
    ##
    #def onReset(self, ec_id):
    #
    #    return RTC.RTC_OK
    
    ###
    ## 
    ## The state update action that is invoked after onExecute() action
    ##
    ## @param ec_id target ExecutionContext Id
    ##
    ## @return RTC::ReturnCode_t
    ##

    ##
    #def onStateUpdate(self, ec_id):
    #
    #    return RTC.RTC_OK
    
    ###
    ##
    ## The action that is invoked when execution context's rate is changed
    ##
    ## @param ec_id target ExecutionContext Id
    ##
    ## @return RTC::ReturnCode_t
    ##
    ##
    #def onRateChanged(self, ec_id):
    #
    #    return RTC.RTC_OK
    



def TaskPlanningRTCInit(manager):
    profile = OpenRTM_aist.Properties(defaults_str=taskplanningrtc_spec)
    manager.registerFactory(profile,
                            TaskPlanningRTC,
                            OpenRTM_aist.Delete)

def MyModuleInit(manager):
    TaskPlanningRTCInit(manager)

    # create instance_name option for createComponent()
    instance_name = [i for i in sys.argv if "--instance_name=" in i]
    if instance_name:
        args = instance_name[0].replace("--", "?")
    else:
        args = ""
  
    # Create a component
    comp = manager.createComponent("TaskPlanningRTC" + args)

def main():
    # remove --instance_name= option
    argv = [i for i in sys.argv if not "--instance_name=" in i]
    # Initialize manager
    mgr = OpenRTM_aist.Manager.init(sys.argv)
    mgr.setModuleInitProc(MyModuleInit)
    mgr.activateManager()
    mgr.runManager()

if __name__ == "__main__":
    main()