using UnityEngine;
using System.Collections;

public class TicTacToeGame : MonoBehaviour
{
    private int[,] board = new int[3, 3];
    private int currentPlayer = 0; // 0 for X, 1 for O

    public void Start()
    {
        for (int i = 0; i < 3; i++)
        {
            for (int j = 0; j < 3; j++)
            {
                board[i, j] = 0;
            }
        }
    }

    public void HandleMove(int row, int col)
    {
        if (board[row, col] == 0)
        {
            board[row, col] = currentPlayer;
            currentPlayer = 1 - currentPlayer;

            if (CheckWin())
            {
                Debug.Log("Player " + (currentPlayer == 0 ? "X" : "O") + " wins!");
            }
        }
    }

    private bool CheckWin()
    {
        for (int i = 0; i < 3; i++)
        {
            if (board[i, 0] == board[i, 1] && board[i, 1] == board[i, 2] && board[i, 0] != 0)
                return true;
        }
        for (int i = 0; i < 3; i++)
        {
            if (board[0, i] == board[1, i] && board[1, i] == board[2, i] && board[0, i] != 0)
                return true;
        }
        if (board[0, 0] == board[1, 1] && board[1, 1] == board[2, 2] && board[0, 0] != 0)
            return true;
        if (board[0, 2] == board[1, 1] && board[1, 1] == board[2, 0] && board[0, 2] != 0)
            return true;

        return false;
    }
}