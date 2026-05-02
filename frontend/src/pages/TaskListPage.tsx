// Task 一覧ページ（/）
// REQ-CD-UI-001: 全 Room の Task を一覧表示
// 詳細設計書 §確定 A

import type React from "react";
import type { TaskResponse } from "../api/types";
import { InlineError } from "../components/InlineError";
import { TaskCard } from "../components/TaskCard";
import { useRooms } from "../hooks/useRooms";
import { useTasks } from "../hooks/useTasks";

const empireId = import.meta.env.VITE_EMPIRE_ID as string | undefined;

// Room ごとの Task 一覧を取得して表示するサブコンポーネント
function RoomTaskList({ roomId, roomName }: { roomId: string; roomName: string }) {
  const { data: tasks, isLoading, error, refetch } = useTasks(roomId);

  if (isLoading) {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-gray-600">{roomName}</h2>
        <div className="animate-pulse space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 bg-gray-200 rounded-md" />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-gray-600">{roomName}</h2>
        <InlineError error={error} onRetry={() => void refetch()} />
      </section>
    );
  }

  const taskList: TaskResponse[] = tasks ?? [];

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-gray-600">
        {roomName} <span className="text-gray-400 font-normal">({taskList.length} 件)</span>
      </h2>
      {taskList.length === 0 ? (
        <p className="text-sm text-gray-400 italic py-2">Task はありません。</p>
      ) : (
        <ul className="space-y-2">
          {taskList.map((task) => (
            <li key={task.id}>
              <TaskCard task={task} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function TaskListPage(): React.ReactElement {
  const { data: rooms, isLoading, error, refetch } = useRooms(empireId ?? "");

  if (!empireId) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-gray-900">Task 一覧</h1>
        <InlineError error="VITE_EMPIRE_ID が設定されていません。frontend/.env に VITE_EMPIRE_ID=<uuid> を追加してください。" />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-gray-900">Task 一覧</h1>
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-200 rounded-md" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-gray-900">Task 一覧</h1>
        <InlineError error={error} onRetry={() => void refetch()} />
      </div>
    );
  }

  const roomList = rooms ?? [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-900">Task 一覧</h1>
      {roomList.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Room がありません。</p>
      ) : (
        <div className="space-y-6">
          {roomList.map((room) => (
            <RoomTaskList key={room.id} roomId={room.id} roomName={room.name} />
          ))}
        </div>
      )}
    </div>
  );
}
