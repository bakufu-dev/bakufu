// ルーター設定
// 詳細設計書 §確定 A に従って React Router 7 の createBrowserRouter で定義

import { QueryClient } from "@tanstack/react-query";
import { createBrowserRouter } from "react-router";
import { apiGet } from "./api/client";
import type { GateDetailResponse, RoomResponse, TaskResponse } from "./api/types";
import { Layout } from "./components/Layout";
import { DirectiveNewPage } from "./pages/DirectiveNewPage";
import { ExternalReviewGatePage } from "./pages/ExternalReviewGatePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { TaskDetailPage } from "./pages/TaskDetailPage";
import { TaskListPage } from "./pages/TaskListPage";

export const queryClient = new QueryClient();

const empireId = import.meta.env.VITE_EMPIRE_ID as string | undefined;

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      {
        index: true,
        Component: TaskListPage,
        loader: async () => {
          if (!empireId) return null;
          // rooms を取得し、各 room の tasks を取得
          const rooms = await queryClient.ensureQueryData<RoomResponse[]>({
            queryKey: ["rooms", empireId],
            queryFn: () => apiGet<RoomResponse[]>(`/api/empires/${empireId}/rooms`),
          });
          await Promise.all(
            rooms.map((room) =>
              queryClient.ensureQueryData<TaskResponse[]>({
                queryKey: ["tasks", room.id],
                queryFn: () => apiGet<TaskResponse[]>(`/api/rooms/${room.id}/tasks`),
              }),
            ),
          );
          return null;
        },
      },
      {
        path: "tasks/:taskId",
        Component: TaskDetailPage,
        loader: async ({ params }) => {
          const { taskId } = params;
          if (!taskId) return null;
          await Promise.all([
            queryClient.ensureQueryData<TaskResponse>({
              queryKey: ["task", taskId],
              queryFn: () => apiGet<TaskResponse>(`/api/tasks/${taskId}`),
            }),
            queryClient.ensureQueryData<GateDetailResponse[]>({
              queryKey: ["taskGates", taskId],
              queryFn: () => apiGet<GateDetailResponse[]>(`/api/tasks/${taskId}/gates`),
            }),
          ]);
          return null;
        },
      },
      {
        path: "gates/:gateId",
        Component: ExternalReviewGatePage,
        loader: async ({ params }) => {
          const { gateId } = params;
          if (!gateId) return null;
          await queryClient.ensureQueryData<GateDetailResponse>({
            queryKey: ["gate", gateId],
            queryFn: () => apiGet<GateDetailResponse>(`/api/gates/${gateId}`),
          });
          return null;
        },
      },
      {
        path: "directives/new",
        Component: DirectiveNewPage,
        loader: async () => {
          if (!empireId) return null;
          await queryClient.ensureQueryData<RoomResponse[]>({
            queryKey: ["rooms", empireId],
            queryFn: () => apiGet<RoomResponse[]>(`/api/empires/${empireId}/rooms`),
          });
          return null;
        },
      },
      {
        path: "*",
        Component: NotFoundPage,
      },
    ],
  },
]);
